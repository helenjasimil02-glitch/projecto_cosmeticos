from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import F, Sum
from .models import ItemVenda, ItemCompra, Produto
from django.core.exceptions import ValidationError
from decimal import Decimal

@receiver(post_save, sender=ItemCompra)
def atualizar_entrada_stock(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            produto = instance.produto
            
            # --- CÁLCULO DE CUSTO MÉDIO PONDERADO ---
            qtd_antiga = Decimal(str(produto.stock_actual))
            preco_antigo = Decimal(str(produto.preco_custo))
            
            nova_quantidade = Decimal(str(instance.quantidade))
            novo_preco_compra = Decimal(str(instance.preco_custo))
            
            total_unidades = qtd_antiga + nova_quantidade
            
            if total_unidades > 0:
                valor_total = (qtd_antiga * preco_antigo) + (nova_quantidade * novo_preco_compra)
                custo_medio = (valor_total / total_unidades).quantize(Decimal('0.01'))
                produto.preco_custo = custo_medio
            
            produto.stock_actual += instance.quantidade
            # skip_clean=True porque os signals não devem ser bloqueados
            # pela validação de preço de venda vs custo
            produto.save(skip_clean=True)

    # --- RECALCULAR TOTAL DA COMPRA ---
    compra = instance.compra
    total_calculado = sum(item.quantidade * item.preco_custo for item in compra.itens.all())
    compra.valor_total = Decimal(str(total_calculado)).quantize(Decimal('0.01'))
    type(compra).objects.filter(id=compra.id).update(valor_total=compra.valor_total)

    
# --- SAÍDA DE STOCK (VENDAS) ---
@receiver(post_save, sender=ItemVenda)
def atualizar_saida_stock(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            produto = instance.produto
            
            # Lógica FEFO: baixa as quantidades dos lotes por ordem de validade
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

            produto.stock_actual -= instance.quantidade
            # skip_clean=True pelo mesmo motivo — operação interna do sistema
            produto.save(skip_clean=True)

    # RECALCULAR TOTAL DA VENDA
    venda = instance.venda
    total_calculado = venda.itens.aggregate(
        total=Sum(F('quantidade') * F('preco_unitario'), output_field=models.DecimalField())
    )['total'] or 0
    
    type(venda).objects.filter(id=venda.id).update(valor_total=total_calculado)
