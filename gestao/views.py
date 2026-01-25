import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import *
from django.db.models import Sum, F, Q
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from django.db import transaction

# --- 1. DASHBOARD ESTRATÉGICO ---
@login_required
def dashboard(request):
    hoje = timezone.now().date()
    inicio_mes = hoje.replace(day=1)

    vendas_v = float(Venda.objects.filter(data__gte=inicio_mes).aggregate(Sum('valor_total'))['valor_total__sum'] or 0)
    extras_v = float(ReceitaExtra.objects.filter(data__gte=inicio_mes).aggregate(Sum('valor'))['valor__sum'] or 0)
    entradas = vendas_v + extras_v
    
    compras_v = float(Compra.objects.filter(data__gte=inicio_mes).aggregate(Sum('valor_total'))['valor_total__sum'] or 0)
    despesas_v = float(Despesa.objects.filter(data__gte=inicio_mes).aggregate(Sum('valor'))['valor__sum'] or 0)
    saidas = compras_v + despesas_v
    lucro = entradas - saidas

    valor_stock = float(Produto.objects.aggregate(total=Sum(F('stock_actual') * F('preco_custo')))['total'] or 0)
    capital_giro = lucro + valor_stock

    top_vendas = ItemVenda.objects.values('produto__nome').annotate(total_qtd=Sum('quantidade')).order_by('-total_qtd')[:5]
    
    vendas_diarias = []
    dias_semana = []
    for i in range(6, -1, -1):
        dia = hoje - timedelta(days=i)
        dias_semana.append(dia.strftime('%d/%m'))
        v_dia = Venda.objects.filter(data__date=dia).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
        vendas_diarias.append(float(v_dia))

    context = {
        'entradas': entradas, 'saidas': saidas, 'lucro': lucro,
        'valor_inventario': valor_stock, 'capital_giro': capital_giro,
        'labels_produtos': [item['produto__nome'] for item in top_vendas],
        'dados_produtos': [item['total_qtd'] for item in top_vendas],
        'vendas_diarias': vendas_diarias, 'dias_semana': dias_semana,
        'alertas_stock': Produto.objects.filter(stock_actual__lte=F('stock_minimo'))[:5],
        'alertas_validade': ItemCompra.objects.filter(validade__lte=hoje + timedelta(days=30), quantidade__gt=0).order_by('validade')[:5],
        'status_cor': 'text-success' if lucro >= 0 else 'text-danger'
    }
    return render(request, 'dashboard.html', context)

# --- 2. OPERAÇÕES (VENDA E CARRINHO) ---
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
    return render(request, 'venda.html', {'produtos': Produto.objects.filter(stock_actual__gt=0).order_by('nome')})

# --- 3. LOGÍSTICA E INVENTÁRIO ---
@login_required
def lista_produtos(request):
    query = request.GET.get('q')
    produtos = Produto.objects.filter(Q(nome__icontains=query) | Q(marca__icontains=query)) if query else Produto.objects.all().order_by('nome')
    return render(request, 'produtos.html', {'produtos': produtos, 'query': query})

@login_required
def lista_fornecedores(request):
    return render(request, 'fornecedores.html', {'fornecedores': Fornecedor.objects.all()})

@login_required
def add_fornecedor(request):
    if request.method == "POST":
        Fornecedor.objects.create(nome=request.POST.get('nome'), contacto=request.POST.get('contacto'))
        return redirect('lista_fornecedores')
    return render(request, 'add_generic.html', {'titulo': 'Novo Fornecedor'})

# --- 4. FINANCEIRO INTEGRADO (EXTRATO) ---
@login_required
def extrato_caixa(request):
    movs = []
    # Prefixos: V (Venda), C (Compra), D (Despesa), R (Receita)
    for v in Venda.objects.all(): 
        movs.append({'id': f"V-{v.id}", 'data': v.data.date(), 'raw_id': v.id, 'desc': "Venda", 'tipo': 'Entrada', 'valor': float(v.valor_total), 'cor': 'text-success'})
    
    for e in ReceitaExtra.objects.all(): 
        movs.append({'id': f"R-{e.id}", 'data': e.data, 'raw_id': e.id, 'desc': e.descricao, 'tipo': 'Entrada', 'valor': float(e.valor), 'cor': 'text-success'})
    
    for d in Despesa.objects.all(): 
        movs.append({'id': f"D-{d.id}", 'data': d.data, 'raw_id': d.id, 'desc': d.descricao, 'tipo': 'Saída', 'valor': float(d.valor), 'cor': 'text-danger'})
    
    for c in Compra.objects.all(): 
        movs.append({'id': f"C-{c.id}", 'data': c.data.date(), 'raw_id': c.id, 'desc': "Compra", 'tipo': 'Saída', 'valor': float(c.valor_total), 'cor': 'text-danger'})
    
    movimentacoes = sorted(movs, key=lambda x: (x['data'], x['raw_id']), reverse=True)
    total_e = sum(m['valor'] for m in movimentacoes if m['tipo'] == 'Entrada')
    total_s = sum(m['valor'] for m in movimentacoes if m['tipo'] == 'Saída')
    
    context = {'movimentacoes': movimentacoes, 'saldo_final': total_e - total_s, 'total_entradas': total_e, 'total_saidas': total_s}
    return render(request, 'extrato.html', context)

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

# --- 5. RELATÓRIOS MENSAIS (DRE) ---
@login_required
def relatorios(request):
    vendas_mes = Venda.objects.dates('data', 'month', order='DESC')
    relatorio_final = []
    for d_mes in vendas_mes:
        if d_mes:
            v = Venda.objects.filter(data__month=d_mes.month, data__year=d_mes.year).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
            e = ReceitaExtra.objects.filter(data__month=d_mes.month, data__year=d_mes.year).aggregate(Sum('valor'))['valor__sum'] or 0
            desp = Despesa.objects.filter(data__month=d_mes.month, data__year=d_mes.year).aggregate(Sum('valor'))['valor__sum'] or 0
            comp = Compra.objects.filter(data__month=d_mes.month, data__year=d_mes.year).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
            relatorio_final.append({
                'mes': d_mes, 
                'vendas': float(v) + float(e), 
                'saidas': float(desp) + float(comp), 
                'lucro': (float(v) + float(e)) - (float(desp) + float(comp))
            })
    return render(request, 'relatorios.html', {'relatorio_final': relatorio_final})

@login_required
def lista_vendas(request):
    return render(request, 'lista_vendas.html', {'vendas': Venda.objects.all().order_by('-data')})

@login_required
def ver_fatura(request, venda_id):
    return render(request, 'fatura.html', {'venda': get_object_or_404(Venda, id=venda_id)})