from django.db import models
from django.contrib.auth.models import User

# --- 1. ORGANIZAÇÃO ---
class Categoria(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    def __str__(self): return self.nome
    class Meta: verbose_name_plural = "1. Categorias"

class Fornecedor(models.Model):
    nome = models.CharField(max_length=200)
    contacto = models.CharField(max_length=100, blank=True, null=True)
    def __str__(self): return self.nome
    class Meta: verbose_name_plural = "2. Fornecedores"

# --- 2. O CORAÇÃO DO SISTEMA: PRODUTO ---
class Produto(models.Model):
    nome = models.CharField(max_length=200)
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, verbose_name="Categoria")
    marca = models.CharField(max_length=100, verbose_name="Marca")
    preco_custo = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Preço de Custo (Kz)")
    preco_venda = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço de Venda (Kz)")
    stock_actual = models.IntegerField(default=0, verbose_name="Stock Actual")
    stock_minimo = models.IntegerField(default=5, verbose_name="Stock Mínimo")
    
    def __str__(self): return f"{self.nome} - {self.marca}"

    # --- FUNÇÕES DE INTELIGÊNCIA (O QUE O ADMIN E DASHBOARD PRECISAM) ---
    
    def margem_lucro(self):
        if self.preco_custo and self.preco_custo > 0:
            lucro = self.preco_venda - self.preco_custo
            percentagem = (lucro / self.preco_custo) * 100
            return lucro, percentagem
        return 0, 0

    def valor_total_stock(self):
        return self.stock_actual * self.preco_custo

    def classe_abc(self):
        # Baseado no Preço de Venda para funcionar com stock zero
        v = float(self.preco_venda or 0)
        if v >= 5000: return 'A'
        if v >= 2000: return 'B'
        return 'C'

    def status_giro(self):
        vendas_count = self.itemvenda_set.count()
        # Vamos verificar a data da última compra para saber se o produto é novo
        ultima_compra = self.itemcompra_set.order_by('-compra__data').first()
        
        if vendas_count > 10: return "Rápido ⚡"
        if vendas_count > 0: return "Normal"
        
        # Se não tem vendas, mas entrou há menos de 7 dias, não é estagnado
        if ultima_compra:
            from django.utils import timezone
            dias_na_loja = (timezone.now() - ultima_compra.compra.data).days
            if dias_na_loja <= 7: return "Novo / Recente ✨"
            
        return "Estagnado ⚠️"

    # --- VALIDAÇÕES DE SEGURANÇA ---
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.preco_venda is not None:
            # Só barra o preço se o produto já tiver custo (pós-compra)
            if self.preco_custo > 0 and self.preco_venda < self.preco_custo:
                raise ValidationError({'preco_venda': f"O preço de venda não pode ser menor que o custo ({self.preco_custo} Kz)!"})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "3. Produtos"
        unique_together = ('nome', 'marca')

# --- 3. MOVIMENTAÇÕES ---
class Compra(models.Model):
    data = models.DateTimeField(auto_now_add=True)
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.SET_NULL, null=True)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    class Meta: verbose_name_plural = "4. Compras"

class ItemCompra(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.IntegerField()
    preco_custo = models.DecimalField(max_digits=10, decimal_places=2)
    validade = models.DateField()
    lote = models.CharField(max_length=50, blank=True, null=True)

class Venda(models.Model):
    METODOS_PAGAMENTO = [('DIN', 'Dinheiro'), ('TPA', 'TPA'), ('TRANS', 'Transferência')]
    data = models.DateTimeField(auto_now_add=True)
    utilizador = models.ForeignKey(User, on_delete=models.PROTECT)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    metodo_pagamento = models.CharField(max_length=10, choices=METODOS_PAGAMENTO)
    class Meta: verbose_name_plural = "5. Vendas"

class ItemVenda(models.Model):
    venda = models.ForeignKey(Venda, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.IntegerField()
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    def total_item(self): return self.quantidade * self.preco_unitario

# --- 4. FINANCEIRO ---
class Despesa(models.Model):
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data = models.DateField()
    class Meta: verbose_name_plural = "6. Despesas"

class ReceitaExtra(models.Model):
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data = models.DateField()
    class Meta: verbose_name_plural = "7. Receitas Extras"