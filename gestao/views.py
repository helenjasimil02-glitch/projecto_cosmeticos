from django.shortcuts import render, redirect
from .models import Venda, Despesa, ReceitaExtra, Produto, ItemCompra, Compra # Adicionado Compra aqui
from django.contrib.auth.models import User
from django.db.models import Sum, F
from django.utils import timezone
from datetime import timedelta

def dashboard(request):
    # 1. Cálculos de Receitas (Dinheiro que entrou)
    total_vendas = Venda.objects.aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    total_extras = ReceitaExtra.objects.aggregate(Sum('valor'))['valor__sum'] or 0
    entradas = float(total_vendas + total_extras)

    # 2. Cálculos de Saídas (Dinheiro que saiu para pagar contas e faturas)
    total_despesas = Despesa.objects.aggregate(Sum('valor'))['valor__sum'] or 0
    total_compras_faturas = Compra.objects.aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    saidas = float(total_despesas + total_compras_faturas)

    # 3. Resultado Líquido (O que sobra em caixa)
    lucro = entradas - saidas

    # 4. VALOR DO INVENTÁRIO (Património imobilizado em stock)
    valor_inventario = Produto.objects.aggregate(
        total=Sum(F('stock_actual') * F('preco_custo'))
    )['total'] or 0
    valor_inventario = float(valor_inventario)

    # 5. CAPITAL DE GIRO TOTAL 
    capital_giro = lucro + valor_inventario

    # ALERTAS
    alertas_stock = Produto.objects.filter(stock_actual__lte=F('stock_minimo'))
    hoje = timezone.now().date()
    alertas_validade = ItemCompra.objects.filter(
        validade__lte=hoje + timedelta(days=30), 
        quantidade__gt=0
    ).order_by('validade')

    context = {
        'entradas': entradas,
        'saidas': saidas,
        'lucro': lucro,
        'valor_inventario': valor_inventario,
        'capital_giro': capital_giro,
        'status_cor': 'text-success' if lucro >= 0 else 'text-danger',
        'alertas_stock': alertas_stock,
        'alertas_validade': alertas_validade,
    }
    return render(request, 'dashboard.html', context)

def registrar_venda(request):
    if request.method == "POST":
        # Pega o primeiro utilizador (vendedor) para o registo
        vendedor = User.objects.first() 
        metodo = request.POST.get('metodo_pagamento')
        
        # Cria o cabeçalho da venda
        from .models import ItemVenda
        nova_venda = Venda.objects.create(utilizador=vendedor, metodo_pagamento=metodo)

        # Pega dados do formulário
        produto_id = request.POST.get('produto')
        quantidade = int(request.POST.get('quantidade'))
        produto = Produto.objects.get(id=produto_id)

        # Cria o item (Isto dispara o Signal que baixa o stock e calcula o total)
        ItemVenda.objects.create(
            venda=nova_venda,
            produto=produto,
            quantidade=quantidade,
            preco_unitario=produto.preco_venda
        )
        return redirect('dashboard')

    # Se for GET, mostra apenas produtos que têm stock
    produtos = Produto.objects.filter(stock_actual__gt=0)
    return render(request, 'venda.html', {'produtos': produtos})

def relatorios(request):
    # 1. Procurar todos os meses que têm vendas (Ignora datas vazias)
    vendas_mes = Venda.objects.dates('data', 'month', order='DESC')
    relatorio_final = []

    for data_mes in vendas_mes:
        # GARANTIA: Se a data for válida, processamos
        if data_mes:
            # Filtramos as movimentações deste mês e ano específicos
            vendas = Venda.objects.filter(
                data__month=data_mes.month, 
                data__year=data_mes.year
            ).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
            
            despesas = Despesa.objects.filter(
                data__month=data_mes.month, 
                data__year=data_mes.year
            ).aggregate(Sum('valor'))['valor__sum'] or 0
            
            compras = Compra.objects.filter(
                data__month=data_mes.month, 
                data__year=data_mes.year
            ).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
            
            lucro = float(vendas) - (float(despesas) + float(compras))
            
            relatorio_final.append({
                'mes': data_mes,
                'vendas': vendas,
                'saidas': despesas + compras,
                'lucro': lucro
            })

    return render(request, 'relatorios.html', {'relatorio_final': relatorio_final})

# Adiciona "get_object_or_404" no topo, nas importações
from django.shortcuts import render, redirect, get_object_or_404

# 1. LISTA DE VENDAS (Para ver o histórico e imprimir)
def lista_vendas(request):
    vendas = Venda.objects.all().order_by('-data') # Mostra as mais recentes primeiro
    return render(request, 'lista_vendas.html', {'vendas': vendas})

# 2. VER FATURA (O rascunho do recibo)
def ver_fatura(request, venda_id):
    venda = get_object_or_404(Venda, id=venda_id)
    return render(request, 'fatura.html', {'venda': venda})