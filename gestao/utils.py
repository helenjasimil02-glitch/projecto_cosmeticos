from django.db.models import Sum, F
from .models import Produto, Venda, Compra, Despesa, ReceitaExtra
from datetime import datetime

def obter_resumo_financeiro_mensal():
    mes_atual = datetime.now().month
    ano_atual = datetime.now().year

    # 1. Valor Total do Inventário (Património em Stock)
    produtos = Produto.objects.all()
    valor_inventario = sum(p.valor_total_stock() for p in produtos)

    # 2. Receitas do Mês (Vendas + Extras)
    total_vendas = Venda.objects.filter(data__month=mes_atual, data__year=ano_atual).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    total_extras = ReceitaExtra.objects.filter(data__month=mes_atual, data__year=ano_atual).aggregate(Sum('valor'))['valor__sum'] or 0
    receita_total = total_vendas + total_extras

    # 3. Custos do Mês (Compras de Stock + Despesas Operacionais)
    total_compras = Compra.objects.filter(data__month=mes_atual, data__year=ano_atual).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    total_despesas = Despesa.objects.filter(data__month=mes_atual, data__year=ano_atual).aggregate(Sum('valor'))['valor__sum'] or 0
    custo_total = total_compras + total_despesas

    # 4. Resultado (Lucro Líquido)
    lucro_liquido = receita_total - custo_total

    return {
        'valor_inventario': valor_inventario,
        'receita_total': receita_total,
        'custo_total': custo_total,
        'lucro_liquido': lucro_liquido,
        'margem_geral': (lucro_liquido / receita_total * 100) if receita_total > 0 else 0
    } 