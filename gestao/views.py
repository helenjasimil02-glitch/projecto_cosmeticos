import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Produto, Venda, ItemVenda, ItemCompra, Compra, Fornecedor, Despesa, ReceitaExtra, Categoria
from django.db.models import Sum, F, Q
from django.utils import timezone
from datetime import timedelta
from django.db import transaction

@login_required
def dashboard(request):
    hoje = timezone.now().date()
    inicio_mes = hoje.replace(day=1)
    produtos = Produto.objects.all()

    # --- 1. KPIs DO MÊS ATUAL (DESEMPENHO) ---
    v_mes = float(Venda.objects.filter(data__gte=inicio_mes).aggregate(Sum('valor_total'))['valor_total__sum'] or 0)
    e_mes = float(ReceitaExtra.objects.filter(data__gte=inicio_mes).aggregate(Sum('valor'))['valor__sum'] or 0)
    c_mes = float(Compra.objects.filter(data__gte=inicio_mes).aggregate(Sum('valor_total'))['valor_total__sum'] or 0)
    d_mes = float(Despesa.objects.filter(data__gte=inicio_mes).aggregate(Sum('valor'))['valor__sum'] or 0)
    
    entradas_mes, saidas_mes = (v_mes + e_mes), (c_mes + d_mes)
    lucro_mes = entradas_mes - saidas_mes

    # --- 2. SALDO HISTÓRICO ACUMULADO ---
    total_vendas_geral = float(Venda.objects.aggregate(Sum('valor_total'))['valor_total__sum'] or 0)
    total_extras_geral = float(ReceitaExtra.objects.aggregate(Sum('valor'))['valor__sum'] or 0)
    total_compras_geral = float(Compra.objects.aggregate(Sum('valor_total'))['valor_total__sum'] or 0)
    total_despesas_geral = float(Despesa.objects.aggregate(Sum('valor'))['valor__sum'] or 0)
    
    saldo_caixa_real = (total_vendas_geral + total_extras_geral) - (total_compras_geral + total_despesas_geral)

    # --- 3. PATRIMÓNIO ATUAL ---
    valor_stock = sum(float(p.valor_total_stock()) for p in produtos)
    capital_giro_consolidado = saldo_caixa_real + valor_stock

    # --- 4. INTELIGÊNCIA E GRÁFICOS ---
    capital_estagnado = sum(float(p.valor_total_stock()) for p in produtos if p.status_giro() == "Estagnado ⚠️")
    
    count_a = len([p for p in produtos if p.classe_abc() == 'A' and p.stock_actual > 0])
    count_b = len([p for p in produtos if p.classe_abc() == 'B' and p.stock_actual > 0])
    count_c = len([p for p in produtos if p.classe_abc() == 'C' and p.stock_actual > 0])

    sugestao = [p for p in produtos if p.classe_abc() in ['A', 'B'] and p.stock_actual <= p.stock_minimo]

    vendas_diarias = []
    dias_semana = []
    for i in range(6, -1, -1):
        dia = hoje - timedelta(days=i)
        dias_semana.append(dia.strftime('%d/%m'))
        v = Venda.objects.filter(data__date=dia).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
        vendas_diarias.append(float(v))

    context = {
        'entradas': entradas_mes, 'saidas': saidas_mes, 'lucro': lucro_mes,
        'valor_inventario': valor_stock, 
        'capital_giro': capital_giro_consolidado,
        'capital_estagnado': capital_estagnado,
        'sugestao_compra': sugestao,
        'abc_counts': [count_a, count_b, count_c],
        'vendas_diarias': vendas_diarias, 'dias_semana': dias_semana,
        'alertas_stock': Produto.objects.filter(stock_actual__lte=F('stock_minimo'))[:4],
        'alertas_validade': ItemCompra.objects.filter(validade__lte=hoje + timedelta(days=30), quantidade__gt=0).order_by('validade')[:4],
        'status_cor': 'text-success' if lucro_mes >= 0 else 'text-danger'
    }
    return render(request, 'dashboard.html', context)


@login_required
def registrar_venda(request):
    if request.method == "POST":
        carrinho_json = request.POST.get('carrinho_dados')

        # Validar se o carrinho não está vazio
        if not carrinho_json:
            messages.error(request, "O carrinho está vazio. Adiciona pelo menos um produto.")
            return redirect('registrar_venda')

        try:
            itens = json.loads(carrinho_json)
        except json.JSONDecodeError:
            messages.error(request, "Erro ao processar o carrinho. Tenta novamente.")
            return redirect('registrar_venda')

        if not itens:
            messages.error(request, "O carrinho está vazio. Adiciona pelo menos um produto.")
            return redirect('registrar_venda')

        try:
            with transaction.atomic():
                # ── VALIDAÇÃO DE STOCK ANTES DE CRIAR A VENDA ──
                erros_stock = []
                produtos_venda = []

                for i in itens:
                    # select_for_update bloqueia o registo durante a transação
                    # evita que duas vendas simultâneas esgotem o mesmo stock
                    prod = Produto.objects.select_for_update().get(id=i['id'])
                    qtd_pedida = int(i['quantidade'])

                    if prod.stock_actual < qtd_pedida:
                        erros_stock.append(
                            f"{prod.nome} — stock disponível: {prod.stock_actual} un. (pedido: {qtd_pedida} un.)"
                        )
                    else:
                        produtos_venda.append((prod, qtd_pedida))

                # Se houver qualquer erro de stock, cancela tudo e avisa
                if erros_stock:
                    for erro in erros_stock:
                        messages.error(request, f"Stock insuficiente: {erro}")
                    return redirect('registrar_venda')

                # Tudo ok — criar a venda
                venda = Venda.objects.create(
                    utilizador=request.user,
                    metodo_pagamento=request.POST.get('metodo_pagamento')
                )
                for prod, qtd in produtos_venda:
                    ItemVenda.objects.create(
                        venda=venda,
                        produto=prod,
                        quantidade=qtd,
                        preco_unitario=prod.preco_venda
                    )

            messages.success(request, f"Venda #{venda.id} registada com sucesso!")
            return redirect('ver_fatura', venda_id=venda.id)

        except Exception as e:
            messages.error(request, f"Erro ao registar a venda. Tenta novamente.")
            return redirect('registrar_venda')

    return render(request, 'venda.html', {'produtos': Produto.objects.filter(stock_actual__gt=0)})


@login_required
def extrato_caixa(request):
    movs = []
    for v in Venda.objects.all(): movs.append({'id': f"V-{v.id}", 'data': v.data.date(), 'raw_id': v.id, 'desc': "Venda", 'tipo': 'Entrada', 'valor': float(v.valor_total), 'cor': 'text-success'})
    for e in ReceitaExtra.objects.all(): movs.append({'id': f"R-{e.id}", 'data': e.data, 'raw_id': e.id, 'desc': e.descricao, 'tipo': 'Entrada', 'valor': float(e.valor), 'cor': 'text-success'})
    for d in Despesa.objects.all(): movs.append({'id': f"D-{d.id}", 'data': d.data, 'raw_id': d.id, 'desc': d.descricao, 'tipo': 'Saída', 'valor': float(d.valor), 'cor': 'text-danger'})
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
def planeamento_compras(request):
    produtos = Produto.objects.all().order_by('nome')
    sugestoes = [p for p in produtos if p.stock_actual <= p.stock_minimo or p.classe_abc() == 'A']
    erro = request.GET.get('erro')
    return render(request, 'planeamento.html', {'produtos': produtos, 'sugestoes': sugestoes, 'erro': erro})


@login_required
def relatorios(request):
    vendas_mes = Venda.objects.dates('data', 'month', order='DESC')
    relatorio_final = []
    for d_mes in vendas_mes:
        if d_mes:
            v = Venda.objects.filter(data__month=d_mes.month, data__year=d_mes.year).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
            e = ReceitaExtra.objects.filter(data__month=d_mes.month, data__year=d_mes.year).aggregate(Sum('valor'))['valor__sum'] or 0
            d = Despesa.objects.filter(data__month=d_mes.month, data__year=d_mes.year).aggregate(Sum('valor'))['valor__sum'] or 0
            c = Compra.objects.filter(data__month=d_mes.month, data__year=d_mes.year).aggregate(Sum('valor_total'))['valor_total__sum'] or 0
            relatorio_final.append({'mes': d_mes, 'vendas': float(v)+float(e), 'saidas': float(d)+float(c), 'lucro': float(v)+float(e)-(float(d)+float(c))})
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


@login_required
def add_produto(request):
    if not request.user.is_superuser:
        return redirect('lista_produtos')

    categorias = Categoria.objects.all().order_by('nome')
    errors = {}
    form_data = {}

    if request.method == "POST":
        form_data = request.POST
        nome         = request.POST.get('nome', '').strip()
        marca        = request.POST.get('marca', '').strip()
        categoria_id = request.POST.get('categoria')
        preco_venda  = request.POST.get('preco_venda')
        stock_minimo = request.POST.get('stock_minimo', 5)

        if not nome:
            errors['nome'] = "O nome do produto é obrigatório."
        if not marca:
            errors['marca'] = "A marca é obrigatória."
        if not categoria_id:
            errors['categoria'] = "Selecciona uma categoria."
        if not preco_venda:
            errors['preco_venda'] = "O preço de venda é obrigatório."
        if nome and marca and Produto.objects.filter(nome__iexact=nome, marca__iexact=marca).exists():
            errors['duplicado'] = f"Já existe um produto '{nome}' da marca '{marca}'."

        if not errors:
            try:
                categoria = Categoria.objects.get(id=categoria_id)
                Produto.objects.create(
                    nome=nome,
                    marca=marca,
                    categoria=categoria,
                    preco_venda=preco_venda,
                    stock_minimo=int(stock_minimo),
                )
                messages.success(request, f"Produto '{nome}' criado com sucesso!")
                return redirect('lista_produtos')
            except Exception as e:
                errors['geral'] = f"Erro ao guardar: {str(e)}"

    return render(request, 'add_produto.html', {
        'titulo': 'Novo Produto',
        'categorias': categorias,
        'errors': errors,
        'form_data': form_data,
    })


@login_required
def editar_produto(request, produto_id):
    if not request.user.is_superuser:
        return redirect('lista_produtos')

    produto    = get_object_or_404(Produto, id=produto_id)
    categorias = Categoria.objects.all().order_by('nome')
    errors     = {}

    if request.method == "POST":
        nome         = request.POST.get('nome', '').strip()
        marca        = request.POST.get('marca', '').strip()
        categoria_id = request.POST.get('categoria')
        preco_venda  = request.POST.get('preco_venda')
        stock_minimo = request.POST.get('stock_minimo', 5)

        if not nome:
            errors['nome'] = "O nome do produto é obrigatório."
        if not marca:
            errors['marca'] = "A marca é obrigatória."
        if not categoria_id:
            errors['categoria'] = "Selecciona uma categoria."
        if not preco_venda:
            errors['preco_venda'] = "O preço de venda é obrigatório."
        if nome and marca and Produto.objects.filter(
            nome__iexact=nome, marca__iexact=marca
        ).exclude(id=produto_id).exists():
            errors['duplicado'] = f"Já existe outro produto '{nome}' da marca '{marca}'."

        if not errors:
            try:
                produto.nome         = nome
                produto.marca        = marca
                produto.categoria    = Categoria.objects.get(id=categoria_id)
                produto.preco_venda  = preco_venda
                produto.stock_minimo = int(stock_minimo)
                produto.save()
                messages.success(request, f"Produto '{nome}' atualizado com sucesso!")
                return redirect('lista_produtos')
            except Exception as e:
                errors['geral'] = f"Erro ao guardar: {str(e)}"

    form_data = {
        'nome':        produto.nome,
        'marca':       produto.marca,
        'categoria':   str(produto.categoria_id),
        'preco_venda': produto.preco_venda,
        'stock_minimo': produto.stock_minimo,
    }

    return render(request, 'add_produto.html', {
        'titulo': f'Editar Produto — {produto.nome}',
        'categorias': categorias,
        'errors': errors,
        'form_data': form_data,
        'produto': produto,
    })


@login_required
def add_compra(request):
    if not request.user.is_superuser:
        return redirect('dashboard')

    produtos     = Produto.objects.all().order_by('nome')
    fornecedores = Fornecedor.objects.all().order_by('nome')
    erro = None

    if request.method == "POST":
        fornecedor_id = request.POST.get('fornecedor')
        itens_json    = request.POST.get('itens_dados', '[]')

        try:
            itens = json.loads(itens_json)
        except Exception:
            itens = []

        if not fornecedor_id:
            erro = "Selecciona um fornecedor."
        elif not itens:
            erro = "Adiciona pelo menos um produto à compra."
        else:
            try:
                with transaction.atomic():
                    fornecedor = Fornecedor.objects.get(id=fornecedor_id)
                    compra = Compra.objects.create(fornecedor=fornecedor)
                    for i in itens:
                        produto = Produto.objects.get(id=i['id'])
                        ItemCompra.objects.create(
                            compra=compra,
                            produto=produto,
                            quantidade=int(i['quantidade']),
                            preco_custo=i['preco_custo'],
                            validade=i['validade'],
                            lote=i.get('lote', '') or '',
                        )
                messages.success(request, "Compra registada com sucesso!")
                return redirect('lista_produtos')
            except Exception as e:
                erro = f"Erro ao registar compra: {str(e)}"

    return render(request, 'add_compra.html', {
        'produtos': produtos,
        'fornecedores': fornecedores,
        'erro': erro,
    })


@login_required
def ajuste_stock(request):
    if not request.user.is_superuser:
        return redirect('planeamento_compras')

    if request.method == "POST":
        produto_id = request.POST.get('produto_id')
        tipo       = request.POST.get('tipo')
        quantidade = int(request.POST.get('quantidade', 0))

        try:
            produto = Produto.objects.get(id=produto_id)
            if tipo == 'remover':
                if quantidade > produto.stock_actual:
                    messages.error(request, f"Quantidade superior ao stock actual ({produto.stock_actual} un.).")
                    return redirect('planeamento_compras')
                produto.stock_actual -= quantidade
            else:
                produto.stock_actual += quantidade
            produto.save()
            messages.success(request, f"Stock de '{produto.nome}' ajustado com sucesso.")
        except Exception:
            messages.error(request, "Erro ao ajustar stock. Tenta novamente.")

    return redirect('planeamento_compras')
