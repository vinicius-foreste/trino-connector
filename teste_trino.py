import os
from getpass import getpass
import requests
try:
	import pandas as pd
except Exception:
	pd = None

# opcional: carregue .env em dev (python-dotenv)
try:
	from dotenv import load_dotenv
	load_dotenv()
except Exception:
	pass

# optional keyring support
try:
    import keyring
except Exception:
    keyring = None

HOST = os.environ.get("TRINO_HOST", "trino-gateway.dataeng.bigdata.olxbr.io")
PORT = int(os.environ.get("TRINO_PORT", "443"))
INFO_URL = f"https://{HOST}/v1/info"
STATEMENT_URL = f"https://{HOST}/v1/statement"

def load_credentials():
	username = os.environ.get('TRINO_USER') or os.environ.get('USER') or os.environ.get('USERNAME')
	password = os.environ.get('TRINO_PASSWORD')

	# try keyring if available and password not in env
	if not password and keyring and username:
		try:
			password = keyring.get_password('trino', username)
		except Exception:
			password = None

	# prompt for username if missing
	if not username:
		try:
			username = input('Trino username (enter to skip): ') or None
		except Exception:
			username = None

	# prompt for password if still missing
	if not password:
		try:
			pw = getpass('Senha (enter para pular): ')
			password = pw or None
		except Exception:
			password = None

	return username, password

bearer = os.environ.get("TRINO_BEARER_TOKEN")

# load credentials from env/keyring/getpass
username, password = load_credentials()

def probe_info():
	try:
		resp = requests.get(INFO_URL, timeout=10)
		print("/v1/info ->", resp.status_code, resp.headers.get('Content-Type'))
	except Exception as e:
		print("Erro ao acessar /v1/info:", repr(e))

def probe_statement():
	print('\nProbe /v1/statement (ver cabeçalhos/401)')
	headers = {"X-Trino-User": username}
	try:
		resp = requests.post(STATEMENT_URL, headers=headers, data="SELECT 1", timeout=10)
		print('Status:', resp.status_code)
		for k, v in resp.headers.items():
			print(f"{k}: {v}")
		print('\nBody prefix:')
		print(resp.text[:800])
		# detectar esquema de autenticação se presente
		www = resp.headers.get('WWW-Authenticate', '')
		if www:
			print('\nDetected WWW-Authenticate header:', www)
			if 'basic' in www.lower():
				# tentar Basic se usuário/senha disponíveis
				pw = password
				if not pw:
					try:
						pw = getpass('Senha para testar Basic (enter para pular): ')
					except Exception:
						pw = None
				if pw:
					try:
						print('\nTentando HTTP Basic (requests) usando Authorization header...')
						resp2 = requests.post(STATEMENT_URL, headers=headers, auth=(username, pw), data='SELECT 1', timeout=10)
						print('Basic attempt status:', resp2.status_code)
						print('Body prefix:')
						print(resp2.text[:800])
					except Exception as e:
						print('Erro na tentativa Basic:', repr(e))
				else:
					print('Senha não fornecida; não foi possível tentar Basic.')
	except Exception as e:
		print('Erro na requisição /v1/statement:', repr(e))

def try_pyhive():
	try:
		from pyhive import trino
	except Exception as e:
		print('\npyhive não disponível (pip install pyhive).', repr(e))
		return

	if not password:
		print('\nSenha não fornecida; pulando teste com pyhive.')
		return

	print('\nTentando conectar com pyhive.trino (username+password)...')
	try:
		conn = trino.connect(
			host=HOST,
			port=PORT,
			protocol='https',
			source=os.environ.get('TRINO_SOURCE', 'dataeng-trino-api'),
			username=username,
			password=password,
		)
		cur = conn.cursor()
		cur.execute('SELECT 1')
		rows = cur.fetchall()
		print('pyhive: sucesso, resultado:', rows)
	except Exception as e:
		msg = str(e)
		# Detect permission denied and try a safer subset of columns
		if 'Access Denied' in msg or 'PERMISSION_DENIED' in msg or 'AccessDenied' in msg:
			print('\npyhive: erro de permissão detectado.')
			print('Mensagem original:', msg)
			# try to extract denied columns from message
			import re
			m = re.search(r"\[([^\]]+)\]", msg)
			denied = []
			if m:
				cols_txt = m.group(1)
				# split on commas and strip
				denied = [c.strip() for c in cols_txt.split(',') if c.strip()]
				print('Colunas negadas detectadas:', denied)
			# If TRINO_SAFE_COLUMNS provided, use those first
			safe_env = os.environ.get('TRINO_SAFE_COLUMNS')
			if safe_env:
				candidate = [c.strip() for c in safe_env.split(',') if c.strip()]
			else:
				# try reading available columns from information_schema
				candidate = []
				try:
					info_cur = conn.cursor()
					info_cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='ods' AND table_name='ad'")
					candidate = [r[0] for r in info_cur.fetchall()]
				except Exception:
					# fallback to a small default set that often is allowed
					candidate = ['ad_id_pk', 'price', 'creation_date']
			# pick columns not in denied
			fallback_cols = [c for c in candidate if c not in denied]
			if not fallback_cols:
				print('Nenhuma coluna segura encontrada para tentar automaticamente.')
				print('Peça ao time de dados grant nas colunas necessárias ou uma view com colunas filtradas.')
				return
			# limit to first 8 columns to keep query small
			fallback_cols = fallback_cols[:8]
			print('Tentando subconjunto de colunas:', fallback_cols)
			try:
				q = f"SELECT {', '.join(fallback_cols)} FROM ods.ad LIMIT 10"
				cur.execute(q)
				rows = cur.fetchall()
				print('pyhive: resultado com colunas filtradas:', rows)
			except Exception as e2:
				print('Erro ao tentar subconjunto de colunas:', repr(e2))
			return
		# otherwise, generic error
		print('pyhive: erro ao conectar/executar:', repr(e))

def try_bearer():
	if not bearer:
		print('\nTRINO_BEARER_TOKEN não definido; pulando teste Bearer.')
		return
	print('\nTentando Authorization: Bearer token via HTTP POST...')
	headers = {"Authorization": f"Bearer {bearer}", "X-Trino-User": username}
	try:
		resp = requests.post(STATEMENT_URL, headers=headers, data="SELECT 1", timeout=10)
		print('Status:', resp.status_code)
		print('WWW-Authenticate:', resp.headers.get('WWW-Authenticate'))
		print('Body prefix:')
		print(resp.text[:800])
	except Exception as e:
		print('Erro Bearer:', repr(e))


def run_example_query():
	"""Executa a query de exemplo que existia em `test.py`.

	Ativa quando `TRINO_RUN_EXAMPLE` está definido ("1", "true"). Usa `username`/`password` carregados.
	"""
	run_flag = os.environ.get('TRINO_RUN_EXAMPLE', '').lower()
	if run_flag not in ('1', 'true', 'yes'):
		return

	if pd is None:
		print('\nPandas não instalado; o resultado será impresso como linhas.')

	try:
		from pyhive import trino
	except Exception as e:
		print('\npyhive não disponível; não é possível executar a query de exemplo.', repr(e))
		return

	if not username or not password:
		print('\nCredenciais ausentes; não foi possível executar a query de exemplo.')
		return

	print('\nExecutando query de exemplo (do antigo test.py) ...')
	try:
		conn = trino.connect(
			host=HOST,
			port=PORT,
			protocol='https',
			source=os.environ.get('TRINO_SOURCE', 'dataeng-trino-api'),
			username=username,
			password=password,
		)
		cur = conn.cursor()
		q = "SELECT * FROM ods.ad WHERE year=2019 AND month=12 AND day=25 LIMIT 10"
		cur.execute(q)
		rows = cur.fetchall()
		cols = [c[0] for c in cur.description] if cur.description else None
		if pd is not None:
			df = pd.DataFrame(rows, columns=cols)
			print(df)
		else:
			print(rows)
	except Exception as e:
		print('Erro ao executar query de exemplo:', repr(e))

if __name__ == '__main__':
	print('Host:', HOST)
	probe_info()
	probe_statement()
	# if user provided credentials try pyhive basic auth
	try_pyhive()
	# if provided token try bearer
	try_bearer()

	# optional: run the example query that used to live in test.py
	run_example_query()

	print('\nTeste concluído. Use TRINO_USER/TRINO_PASSWORD ou TRINO_BEARER_TOKEN como variáveis de ambiente para não digitar credenciais.')