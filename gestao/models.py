from django.db import models
from django.contrib.auth.models import User

class Categoria(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.nome
    class Meta:
        verbose_name_plural = "1. Categorias"


class Fornecedor(models.Model):
    nome = models.CharField(max_length=200)
    contacto = models.CharField(max_length=100, blank=True, null=True)
    def __str__(self): return self.nome
    class Meta:
        verbose_name_plural = "2. Fornecedores"

class Produto(models.Model):
    nome = models.CharField(max_length=200)
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, verbose_name="Categoria")
    marca = models.CharField(max_length=100, verbose_name="Marca")
    preco_custo = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Custo Médio (Kz)")
    preco_venda = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço de Venda (Kz)")
    stock_actual = models.IntegerField(default=0, verbose_name="Stock Actual")
    stock_minimo = models.IntegerField(default=5, verbose_name="Stock Mínimo")
    
    def __str__(self): return f"{self.nome} - {self.marca}"

    def margem_lucro(self):
        if self.preco_custo > 0:
            lucro = self.preco_venda - self.preco_custo
            percentagem = (lucro / self.preco_custo) * 100
            return lucro, percentagem
        return 0, 0

    def valor_total_stock(self):
        return self.stock_actual * self.preco_custo

    # O "POLÍCIA" DO ADMIN: Esta função mostra o erro vermelho no ecrã
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.preco_venda < self.preco_custo:
            raise ValidationError({
                'preco_venda': f"O preço de venda ({self.preco_venda}) não pode ser inferior ao custo médio ({self.preco_custo})!"
            })

    # GARANTE A GRAVAÇÃO SEGURA
    def save(self, *args, **kwargs):
        self.full_clean() # Força a execução do 'clean' antes de gravar
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "3. Produtos"
        unique_together = ('nome', 'marca')

class Compra(models.Model):
    data = models.DateTimeField(auto_now_add=True)
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.SET_NULL, null=True)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    def __str__(self): return f"Compra {self.id} ({self.data.strftime('%d/%m/%Y')})"
    class Meta:
        verbose_name_plural = "4. Compras"

class ItemCompra(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.IntegerField()
    preco_custo = models.DecimalField(max_digits=10, decimal_places=2)
    validade = models.DateField()
    lote = models.CharField(max_length=50, blank=True, null=True)

class Venda(models.Model):
    METODOS_PAGAMENTO = [('DIN', 'Dinheiro'), ('TPA', 'TPA / Multicaixa'), ('TRANS', 'Transferência')]
    data = models.DateTimeField(auto_now_add=True)
    utilizador = models.ForeignKey(User, on_delete=models.PROTECT)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    metodo_pagamento = models.CharField(max_length=10, choices=METODOS_PAGAMENTO)
    def __str__(self): return f"Venda {self.id} - {self.data}"
    class Meta:
        verbose_name_plural = "5. Vendas"

class ItemVenda(models.Model):
    venda = models.ForeignKey(Venda, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.IntegerField()
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    def total_item(self):
        return self.quantidade * self.preco_unitario
    
    def clean(self):
        if self.quantidade > self.produto.stock_actual:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Stock insuficiente para {self.produto.nome}. Disponível: {self.produto.stock_actual}")

class Despesa(models.Model):
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data = models.DateField()
    def __str__(self): return f"{self.descricao} ({self.valor})"
    class Meta:
        verbose_name_plural = "6. Despesas"

class ReceitaExtra(models.Model):
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data = models.DateField()
    def __str__(self): return f"Receita Extra: {self.descricao}"
    class Meta:
        verbose_name_plural = "7. Receitas Extras"