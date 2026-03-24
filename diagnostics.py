"""Diagnósticos para conectividade com o gateway Trino.

Fornece:
- `tcp_probe(host, port, timeout)` — testa handshake TCP (connect).
- `http_head_probe(url, timeout)` — faz HEAD e retorna status + headers.
- CLI simples para resumir os cheques e imprimir `WWW-Authenticate` quando presente.

Use localmente para distinguir problemas de rede (TCP/TLS) de problemas de autenticação (HTTP 401 + WWW-Authenticate).
Como se encaixa na prática

diagnostics -> checa TCP/TLS e retorna headers HTTP (inclui WWW-Authenticate).
trino_connect (TrinoClient) -> faz a conexão real e executa queries.
Orquestrador/test.py -> chama diagnostics, interpreta o resultado e então decide:
se TCP falhou → aborta e pede verificação de rede/VPN/DNS;
se WWW-Authenticate indica Negotiate/Kerberos → não tentar username/password (usar SSO/infra);
se WWW-Authenticate indica Basic → prosseguir com load_credentials() + TrinoClient.connect().
Exemplo mínimo de uso (cole em test.py):

O que é: cabeçalho HTTP enviado pelo servidor quando exige autenticação. Indica qual esquema de autenticação o cliente deve usar.
Onde aparece: em respostas com status 401 Unauthorized (às vezes em 407 Proxy Authentication Required

O que o cliente faz: responde com o cabeçalho Authorization: <scheme> <credentials> apropriado (ex.: Authorization: Basic <base64>, ou Authorization: Bearer <token>). Para Negotiate/Kerberos o fluxo é de SSO (tickets), não user+password simples.
Como interpretar ao diagnosticar:
Basic → pode tentar usuário + senha.
Bearer → precisa de token/OAuth — obtenha token via fluxo apropriado.
Negotiate / Kerberos → SSO/Kerberos; configure kinit/keytab ou SSPI (Windows).
Sem WWW-Authenticate mas 401 → servidor mal configurado ou proxy interferindo.
"""
from __future__ import annotations

import argparse
import socket
from typing import Dict, Optional, Tuple

import requests
from requests.exceptions import SSLError, RequestException


def tcp_probe(host: str, port: int = 443, timeout: float = 5.0) -> Tuple[bool, Optional[str]]:
    """Tenta abrir uma conexão TCP a `host:port`.

    Retorna (ok, error). `ok` é True se a conexão TCP foi estabelecida.
    Em caso de falha `error` contém a descrição.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, None
    except Exception as e:
        return False, str(e)


def http_head_probe(url: str, timeout: float = 5.0) -> Tuple[Optional[int], Dict[str, str], Optional[str]]:
    """Faz uma requisição HTTP HEAD para `url` e retorna (status_code, headers, error).

    `headers` é um dict simples (str->str). Em caso de timeout/erro, `error` contém a mensagem.
    """
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        # normalize headers to str->str
        headers = {k: v for k, v in resp.headers.items()}
        return resp.status_code, headers, None
    except SSLError as e:
        return None, {}, f"TLS/SSL error: {e}"
    except RequestException as e:
        return None, {}, str(e)


def summarize_probe(host: str, port: int = 443, timeout: float = 5.0) -> Dict[str, object]:
    """Executa tcp_probe + http_head_probe (usando https://host) e retorna um resumo."""
    tcp_ok, tcp_err = tcp_probe(host, port=port, timeout=timeout)
    url = f"https://{host}"
    status, headers, http_err = http_head_probe(url, timeout=timeout)

    result = {
        "host": host,
        "port": port,
        "tcp_ok": tcp_ok,
        "tcp_error": tcp_err,
        "http_status": status,
        "http_error": http_err,
        "http_headers": headers,
    }
    return result


def _print_summary(d: Dict[str, object]) -> None:
    print(f"Host: {d['host']}:{d['port']}")
    print(f"TCP connect: {'OK' if d['tcp_ok'] else 'FAILED'}")
    if d['tcp_error']:
        print('  TCP error:', d['tcp_error'])
    if d['http_status'] is not None:
        print('HTTP status:', d['http_status'])
        if isinstance(d['http_headers'], dict) and d['http_headers']:
            if 'WWW-Authenticate' in d['http_headers']:
                wa = d['http_headers']['WWW-Authenticate']
                print('WWW-Authenticate:', wa)
                # quick guidance
                low = wa.lower()
                if 'negotiate' in low or 'kerberos' in low:
                    print('  -> Server requires Negotiate/Kerberos (SSO). User/password may not work.')
                elif 'bearer' in low:
                    print('  -> Server requires Bearer token/OAuth.')
                elif 'basic' in low:
                    print('  -> Server accepts Basic auth (username/password).')
            else:
                print('Returned headers:')
                for k, v in d['http_headers'].items():
                    print(f'  {k}: {v}')
    else:
        print('HTTP probe failed:', d['http_error'])


def main() -> None:
    parser = argparse.ArgumentParser(description='Diagnostics for Trino gateway connectivity')
    parser.add_argument('--host', '-H', required=True, help='Hostname of the Trino gateway')
    parser.add_argument('--port', '-p', type=int, default=443, help='TCP port (default: 443)')
    parser.add_argument('--timeout', '-t', type=float, default=5.0, help='Probe timeout seconds')
    parser.add_argument('--scheme', '-s', choices=['http', 'https'], default='https', help='URL scheme to use for HTTP probe')
    args = parser.parse_args()
    # build summary but allow custom scheme
    # if user passed a full URL as host, use it directly for HTTP probe
    summary = summarize_probe(args.host, port=args.port, timeout=args.timeout)
    # inject scheme-aware URL in summary for clarity
    summary['_used_url'] = f"{args.scheme}://{args.host}"
    _print_summary(summary)

if __name__ == '__main__':
    main()
