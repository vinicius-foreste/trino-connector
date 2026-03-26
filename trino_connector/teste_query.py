from trino_connect import TrinoClient

cliente = TrinoClient(host="trino-gateway.dataeng.bigdata.olxbr.io")

cliente.connect("vinicius.foreste", "senha")

minha_pesquisa = "SELECT * FROM ods.ad LIMIT 100"

tabela_de_dados = cliente.execute(minha_pesquisa)

print(tabela_de_dados.head())

cliente.close()
