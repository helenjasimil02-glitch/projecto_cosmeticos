from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import F, Sum
from .models import ItemVenda, ItemCompra, Produto
from django.core.exceptions import ValidationError

# --- 1. ENTRADA DE STOCK (COMPRAS) ---
@receiver(post_save, sender=ItemCompra)
def atualizar_entrada_stock(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            produto = instance.produto
            
            # Cálculo do Custo Médio Ponderado (RF05/RF08)
            qtd_antiga = produto.stock_actual
            preco_antigo = produto.preco_custo
            total_unidades = qtd_antiga + instance.quantidade
            
            if total_unidades > 0:
                custo_medio = ((qtd_antiga * preco_antigo) + (instance.quantidade * instance.preco_custo)) / total_unidades
                produto.preco_custo = custo_medio
            
            # Atualiza o Stock Físico (RF02)
            produto.stock_actual += instance.quantidade
            produto.save()

    # RECALCULAR TOTAL DA COMPRA (Garante que nunca fica 0.00)
    compra = instance.compra
    # Agregamos a soma de (quantidade * preco) de todos os itens ligados a esta compra
    total_calculado = compra.itens.aggregate(
        total=Sum(F('quantidade') * F('preco_custo'), output_field=models.DecimalField())
    )['total'] or 0
    
    # Atualiza o campo valor_total da Compra sem disparar o signal novamente (usando update)
    # Isso evita o loop infinito e garante que o valor aparece no banco
    type(compra).objects.filter(id=compra.id).update(valor_total=total_calculado)


# --- 2. SAÍDA DE STOCK (VENDAS) ---
@receiver(post_save, sender=ItemVenda)
def atualizar_saida_stock(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            produto = instance.produto
            
            # Lógica FEFO: Baixa as quantidades dos lotes individuais (RF03)
            quantidade_a_baixar = instance.quantidade
            lotes = ItemCompra.objects.filter(produto=produto, quantidade__gt=0).order_by('validade')
            
            for lote in lotes:
                if quantidade_a_baixar <= 0: break
                if lote.quantidade >= quantidade_a_baixar:
                    lote.quantidade -= quantidade_a_baixar
                    quantidade_a_baixar = 0
                else:
                    quantidade_a_baixar -= lote.quantidade
                    lote.quantidade = 0
                lote.save()

            # Atualiza o Saldo Global do Produto (RF02)
            produto.stock_actual -= instance.quantidade
            produto.save()

    # RECALCULAR TOTAL DA VENDA (RF06)
    venda = instance.venda
    total_calculado = venda.itens.aggregate(
        total=Sum(F('quantidade') * F('preco_unitario'), output_field=models.DecimalField())
    )['total'] or 0
    
    type(venda).objects.filter(id=venda.id).update(valor_total=total_calculado)