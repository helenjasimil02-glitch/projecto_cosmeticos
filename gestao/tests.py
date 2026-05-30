from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal
from .models import Categoria, Fornecedor, Produto, Compra, ItemCompra, Venda, ItemVenda


class TestCustoMedioPonderado(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nome="Skincare")
        self.produto = Produto.objects.create(
            nome="Creme Teste", marca="Marca X",
            categoria=self.categoria, preco_venda=Decimal('5000.00')
        )
        self.fornecedor = Fornecedor.objects.create(nome="Fornecedor Teste")

    def test_primeira_compra_define_custo(self):
        compra = Compra.objects.create(fornecedor=self.fornecedor)
        ItemCompra.objects.create(
            compra=compra, produto=self.produto,
            quantidade=10, preco_custo=Decimal('1000.00'),
            validade='2027-01-01'
        )
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.preco_custo, Decimal('1000.00'))
        self.assertEqual(self.produto.stock_actual, 10)

    def test_custo_medio_ponderado_segunda_compra(self):
        compra1 = Compra.objects.create(fornecedor=self.fornecedor)
        ItemCompra.objects.create(
            compra=compra1, produto=self.produto,
            quantidade=10, preco_custo=Decimal('1000.00'),
            validade='2027-01-01'
        )
        compra2 = Compra.objects.create(fornecedor=self.fornecedor)
        ItemCompra.objects.create(
            compra=compra2, produto=self.produto,
            quantidade=10, preco_custo=Decimal('2000.00'),
            validade='2027-06-01'
        )
        self.produto.refresh_from_db()
        # Custo médio = (10*1000 + 10*2000) / 20 = 1500
        self.assertEqual(self.produto.preco_custo, Decimal('1500.00'))
        self.assertEqual(self.produto.stock_actual, 20)


class TestFEFO(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nome="Skincare")
        self.produto = Produto.objects.create(
            nome="Sérum Teste", marca="Marca Y",
            categoria=self.categoria, preco_venda=Decimal('3000.00')
        )
        self.fornecedor = Fornecedor.objects.create(nome="Fornecedor FEFO")
        self.user = User.objects.create_user(username='vendedor', password='teste123')

        # Lote 1 — vence primeiro
        compra1 = Compra.objects.create(fornecedor=self.fornecedor)
        ItemCompra.objects.create(
            compra=compra1, produto=self.produto,
            quantidade=5, preco_custo=Decimal('1000.00'),
            validade='2026-06-01'
        )
        # Lote 2 — vence depois
        compra2 = Compra.objects.create(fornecedor=self.fornecedor)
        ItemCompra.objects.create(
            compra=compra2, produto=self.produto,
            quantidade=5, preco_custo=Decimal('1000.00'),
            validade='2027-01-01'
        )

    def test_fefo_consome_lote_mais_antigo_primeiro(self):
        venda = Venda.objects.create(
            utilizador=self.user,
            metodo_pagamento='DIN'
        )
        ItemVenda.objects.create(
            venda=venda, produto=self.produto,
            quantidade=3, preco_unitario=Decimal('3000.00')
        )
        lote_antigo = ItemCompra.objects.get(validade='2026-06-01')
        lote_novo = ItemCompra.objects.get(validade='2027-01-01')
        # Lote antigo deve ter sido consumido primeiro
        self.assertEqual(lote_antigo.quantidade, 2)
        self.assertEqual(lote_novo.quantidade, 5)

    def test_fefo_consome_dois_lotes_se_necessario(self):
        venda = Venda.objects.create(
            utilizador=self.user,
            metodo_pagamento='DIN'
        )
        ItemVenda.objects.create(
            venda=venda, produto=self.produto,
            quantidade=7, preco_unitario=Decimal('3000.00')
        )
        lote_antigo = ItemCompra.objects.get(validade='2026-06-01')
        lote_novo = ItemCompra.objects.get(validade='2027-01-01')
        # Lote antigo esgotado, lote novo consumiu 2
        self.assertEqual(lote_antigo.quantidade, 0)
        self.assertEqual(lote_novo.quantidade, 3)


class TestValidacaoStock(TestCase):
    def setUp(self):
        self.categoria = Categoria.objects.create(nome="Perfumes")
        self.produto = Produto.objects.create(
            nome="Perfume Teste", marca="Marca Z",
            categoria=self.categoria, preco_venda=Decimal('8000.00'),
            stock_actual=5
        )

    def test_stock_nao_fica_negativo(self):
        from django.test import Client
        from django.contrib.auth.models import User
        user = User.objects.create_user(username='admin_test', password='teste123', is_superuser=True)
        client = Client()
        client.login(username='admin_test', password='teste123')
        import json
        carrinho = [{'id': self.produto.id, 'quantidade': 10, 'preco': 8000}]
        response = client.post('/venda/', {
            'carrinho_dados': json.dumps(carrinho),
            'metodo_pagamento': 'DIN'
        })
        self.produto.refresh_from_db()
        self.assertGreaterEqual(self.produto.stock_actual, 0)