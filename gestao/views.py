import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import *
from django.db.models import Sum, F, Q
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from django.db import transaction

@login_required
def dashboard(request):
    hoje = timezone.now().date()
    inicio_mes = hoje.replace(day=1)
    produtos = Produto.objects.all()

    # 1. KPIs FINANCEIROS
    v_mes = float(Venda.objects.filter(data__gte=inicio_mes).aggregate(Sum('valor_total'))['valor_total__sum'] or 0)
    e_mes = float(ReceitaExtra.objects.filter(data__gte=inicio_mes).aggregate(Sum('valor'))['valor__sum'] or 0)
    c_mes = float(Compra.objects.filter(data__gte=inicio_mes).aggregate(Sum('valor_total'))['valor_total__sum'] or 0)
    d_mes = float(Despesa.objects.filter(data__gte=inicio_mes).aggregate(Sum('valor'))['valor__sum'] or 0)
    
    entradas, saidas = (v_mes + e_mes), (c_mes + d_mes)
    lucro = entradas - saidas

    # 2. PATRIMÓNIO E RISCO (Sincronizado com a tua pesquisa)
    valor_stock = sum(float(p.valor_total_stock()) for p in produtos)
    # Capital estagnado ignora produtos marcados como "Novo"
    capital_estagnado = sum(float(p.valor_total_stock()) for p in produtos if p.status_giro() == "Estagnado ⚠️")
    
    # 3. GRÁFICO ABC (Apenas o que tem stock para não distorcer o impacto atual)
    count_a = len([p for p in produtos if p.classe_abc() == 'A' and p.stock_actual > 0])
    count_b = len([p for p in produtos if p.classe_abc() == 'B' and p.stock_actual > 0])
    count_c = len([p for p in produtos if p.classe_abc() == 'C' and p.stock_actual > 0])

    context = {
        'entradas': entradas, 'saidas': saidas, 'lucro': lucro,
        'valor_inventario': valor_stock, 'capital_giro': lucro + valor_stock,
        'capital_estagnado': capital_estagnado,
        'abc_counts': [count_a, count_b, count_c],
        'alertas_stock': Produto.objects.filter(stock_actual__lte=F('stock_minimo'))[:4],
        'alertas_validade': ItemCompra.objects.filter(validade__lte=hoje + timedelta(days=30), quantidade__gt=0).order_by('validade')[:4],
        'status_cor': 'text-success' if lucro >= 0 else 'text-danger'
    }
    return render(request, 'dashboard.html', context)

# NOVA VIEW: PLANEAMENTO ESTRATÉGICO
@login_required
def planeamento_compras(request):
    produtos = Produto.objects.all().order_by('nome')
    # Sugestão: Itens A ou B que estão com stock baixo
    sugestoes = [p for p in produtos if p.classe_abc() in ['A', 'B'] and p.stock_actual <= p.stock_minimo]
    return render(request, 'planeamento.html', {'produtos': produtos, 'sugestoes': sugestoes})

@login_required
def registrar_venda(request):
    if request.method == "POST":
        carrinho_json = request.POST.get('carrinho_dados')
        itens = json.loads(carrinho_json)
        with transaction.atomic():
            venda = Venda.objects.create(utilizador=request.user, metodo_pagamento=request.POST.get('metodo_pagamento'))
            for i in itens:
                prod = Produto.objects.get(id=i['id'])
                ItemVenda.objects.create(venda=venda, produto=prod, quantidade=int(i['quantidade']), preco_unitario=prod.preco_venda)
        return redirect('dashboard')
    return render(request, 'venda.html', {'produtos': Produto.objects.filter(stock_actual__gt=0)})

@login_required
def extrato_caixa(request):
    movs = []
    for v in Venda.objects.all(): movs.append({'id': f"V-{v.id}", 'data': v.data.date(), 'raw_id': v.id, 'desc': "Venda", 'tipo': 'Entrada', 'valor': float(v.valor_total), 'cor': 'text-success'})
    for e in ReceitaExtra.objects.all(): movs.append({'id': f"R-{e.id}", 'data': e.data, 'raw_id': e.id, 'desc': e.descricao, 'tipo': 'Entrada', 'valor': float(e.valor), 'cor': 'text-success'})
    for d in Despesa.objects.all(): movs.append({'id': d.id, 'data': d.data, 'desc': d.descricao, 'tipo': 'Saída', 'valor': float(d.valor), 'cor': 'text-danger'})
    for c in Compra.objects.all(): movs.append({'id': f"C-{c.id}", 'data': c.data.date(), 'raw_id': c.id, 'desc': "Compra", 'tipo': 'Saída', 'valor': float(c.valor_total), 'cor': 'text-danger'})
    movimentacoes = sorted(movs, key=lambda x: (x['data'], x['raw_id']), reverse=True)
    t_e = sum(m['valor'] for m in movimentacoes if m['tipo'] == 'Entrada')
    t_s = sum(m['valor'] for m in movimentacoes if m['tipo'] == 'Saída')
    return render(request, 'extrato.html', {'movimentacoes': movimentacoes, 'saldo_final': t_e - t_s, 'total_entradas': t_e, 'total_saidas': t_s})

@login_required
def lista_produtos(request):
    query = request.GET.get('q')
    produtos = Produto.objects.filter(Q(nome__icontains=query) | Q(marca__icontains=query)) if query else Produto.objects.all()
    return render(request, 'produtos.html', {'produtos': produtos, 'query': query})

@login_required
def relatorios(request):
    vendas_mes = Venda.objects.dates('data', 'month', order='DESC')
    relatorio_final = []
    for data_mes in vendas_mes:
        if data_mes:
            v = Venda.objects.filter(data__month=data_mes.month, data__year=data_mes.year).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
            d = Despesa.objects.filter(data__month=data_mes.month, data__year=data_mes.year).aggregate(Sum('valor'))['valor__sum'] or 0
            c = Compra.objects.filter(data__month=data_mes.month, data__year=data_mes.year).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
            relatorio_final.append({'mes': data_mes, 'vendas': float(v), 'saidas': float(d)+float(c), 'lucro': float(v)-(float(d)+float(c))})
    return render(request, 'relatorios.html', {'relatorio_final': relatorio_final})

@login_required
def lista_vendas(request): return render(request, 'lista_vendas.html', {'vendas': Venda.objects.all().order_by('-data')})
@login_required
def ver_fatura(request, venda_id): return render(request, 'fatura.html', {'venda': get_object_or_404(Venda, id=venda_id)})
@login_required
def lista_fornecedores(request): return render(request, 'fornecedores.html', {'fornecedores': Fornecedor.objects.all()})
@login_required
def add_fornecedor(request):
    if request.method == "POST":
        Fornecedor.objects.create(nome=request.POST.get('nome'), contacto=request.POST.get('contacto'))
        return redirect('lista_fornecedores')
    return render(request, 'add_generic.html', {'titulo': 'Novo Fornecedor'})
@login_required
def add_despesa(request):
    if request.method == "POST":
        Despesa.objects.create(descricao=request.POST.get('descricao'), valor=request.POST.get('valor'), data=timezone.now())
        return redirect('extrato_caixa')
    return render(request, 'add_generic.html', {'titulo': 'Nova Despesa'})
@login_required
def add_receita(request):
    if request.method == "POST":
        ReceitaExtra.objects.create(descricao=request.POST.get('descricao'), valor=request.POST.get('valor'), data=timezone.now())
        return redirect('extrato_caixa')
    return render(request, 'add_generic.html', {'titulo': 'Nova Receita Extra'})