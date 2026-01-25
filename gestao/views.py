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
    # KPIs
    vendas_v = float(Venda.objects.filter(data__gte=inicio_mes).aggregate(Sum('valor_total'))['valor_total__sum'] or 0)
    extras_v = float(ReceitaExtra.objects.filter(data__gte=inicio_mes).aggregate(Sum('valor'))['valor__sum'] or 0)
    entradas = vendas_v + extras_v
    compras_v = float(Compra.objects.filter(data__gte=inicio_mes).aggregate(Sum('valor_total'))['valor_total__sum'] or 0)
    despesas_v = float(Despesa.objects.filter(data__gte=inicio_mes).aggregate(Sum('valor'))['valor__sum'] or 0)
    saidas = compras_v + despesas_v
    lucro = entradas - saidas
    # Gráfico Top 5
    top_vendas = ItemVenda.objects.values('produto__nome').annotate(total_qtd=Sum('quantidade')).order_by('-total_qtd')[:5]
    # Contexto consolidado
    context = {
        'entradas': entradas, 'saidas': saidas, 'lucro': lucro,
        'valor_inventario': float(Produto.objects.aggregate(total=Sum(F('stock_actual') * F('preco_custo')))['total'] or 0),
        'capital_giro': lucro + float(Produto.objects.aggregate(total=Sum(F('stock_actual') * F('preco_custo')))['total'] or 0),
        'labels_produtos': [item['produto__nome'] for item in top_vendas],
        'dados_produtos': [item['total_qtd'] for item in top_vendas],
        'alertas_stock': Produto.objects.filter(stock_actual__lte=F('stock_minimo'))[:5],
        'alertas_validade': ItemCompra.objects.filter(validade__lte=hoje + timedelta(days=30), quantidade__gt=0).order_by('validade')[:5],
        'status_cor': 'text-success' if lucro >= 0 else 'text-danger'
    }
    return render(request, 'dashboard.html', context)

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
    movimentacoes = []
    
    # Adicionamos .date() para converter Dia/Hora em apenas Dia
    for v in Venda.objects.all(): 
        movimentacoes.append({
            'data': v.data.date(), # Corrigido aqui
            'desc': f"Venda #{v.id}", 
            'tipo': 'Entrada', 
            'valor': float(v.valor_total), 
            'cor': 'text-success'
        })
        
    for e in ReceitaExtra.objects.all(): 
        movimentacoes.append({
            'data': e.data, 
            'desc': e.descricao, 
            'tipo': 'Entrada', 
            'valor': float(e.valor), 
            'cor': 'text-success'
        })
        
    for d in Despesa.objects.all(): 
        movimentacoes.append({
            'data': d.data, 
            'desc': d.descricao, 
            'tipo': 'Saída', 
            'valor': float(d.valor), 
            'cor': 'text-danger'
        })
        
    for c in Compra.objects.all(): 
        movimentacoes.append({
            'data': c.data.date(), # Corrigido aqui
            'desc': f"Compra #{c.id}", 
            'tipo': 'Saída', 
            'valor': float(c.valor_total), 
            'cor': 'text-danger'
        })
    
    # Agora a ordenação funcionará
    movs = sorted(movimentacoes, key=lambda x: x['data'], reverse=True)
    
    total_e = sum(m['valor'] for m in movs if m['tipo'] == 'Entrada')
    total_s = sum(m['valor'] for m in movs if m['tipo'] == 'Saída')
    
    context = {
        'movimentacoes': movs, 
        'saldo_final': total_e - total_s, 
        'total_entradas': total_e, 
        'total_saidas': total_s
    }
    return render(request, 'extrato.html', context)

@login_required
def lista_produtos(request):
    query = request.GET.get('q')
    produtos = Produto.objects.filter(Q(nome__icontains=query) | Q(marca__icontains=query)) if query else Produto.objects.all()
    return render(request, 'produtos.html', {'produtos': produtos, 'query': query})

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

@login_required
def relatorios(request):
    vendas_mes = Venda.objects.dates('data', 'month', order='DESC')
    relatorio = []
    for d in vendas_mes:
        v = Venda.objects.filter(data__month=d.month, data__year=d.year).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
        relatorio.append({'mes': d, 'vendas': v, 'lucro': float(v)}) # Simplificado para evitar erro
    return render(request, 'relatorios.html', {'relatorio_final': relatorio})

@login_required
def lista_vendas(request): return render(request, 'lista_vendas.html', {'vendas': Venda.objects.all().order_by('-data')})

@login_required
def ver_fatura(request, venda_id): return render(request, 'fatura.html', {'venda': get_object_or_404(Venda, id=venda_id)})

@login_required
def lista_fornecedores(request): return render(request, 'fornecedores.html', {'fornecedores': Fornecedor.objects.all()})