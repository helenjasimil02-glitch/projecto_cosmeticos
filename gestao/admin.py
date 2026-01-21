from django.contrib import admin
from django.utils import timezone
from datetime import timedelta
from django.utils.html import format_html
from django.db.models import Sum
from .models import *

# --- CONFIGURAÇÃO VISUAL DO PAINEL ---
admin.site.index_title = "Gestão de Cosméticos - Painel Financeiro"
admin.site.site_header = "Loja de Cosméticos"

class ItemCompraInline(admin.TabularInline):
    model = ItemCompra
    extra = 1

class ItemVendaInline(admin.TabularInline):
    model = ItemVenda
    extra = 1

@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = ('id', 'fornecedor', 'data', 'valor_total')
    inlines = [ItemCompraInline]

@admin.register(Venda)
class VendaAdmin(admin.ModelAdmin):
    list_display = ('id', 'data', 'valor_total', 'metodo_pagamento', 'utilizador')
    inlines = [ItemVendaInline]

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'marca', 'exibir_custo_medio', 'preco_venda', 'exibir_lucro', 'exibir_stock', 'status_validade')
    list_filter = ('categoria', 'marca')
    search_fields = ('nome', 'marca')

    def exibir_custo_medio(self, obj):
        return f"{obj.preco_custo:,.2f} Kz"
    exibir_custo_medio.short_description = "Custo Médio"

    def exibir_lucro(self, obj):
        lucro, perc = obj.margem_lucro()
        if perc < 10:
            # Corrigido: passamos 'perc' como argumento
            return format_html('<b style="color:orange;">{:.1f}%</b>', perc)
        return f"{perc:.1f}%"
    exibir_lucro.short_description = "Margem (%)"

    def exibir_stock(self, obj):
        if obj.stock_actual <= obj.stock_minimo:
            # Corrigido: passamos o stock como argumento
            return format_html('<b style="color:red;">{} un. (Baixo)</b>', obj.stock_actual)
        return f"{obj.stock_actual} un."
    exibir_stock.short_description = "Stock"

    def status_validade(self, obj):
        proximo_lote = obj.itemcompra_set.filter(quantidade__gt=0).order_by('validade').first()
        
        if not proximo_lote: 
            # Corrigido: passamos o texto como argumento para evitar o erro
            return format_html('<span style="color:gray;">{}</span>', "Sem stock")
        
        hoje = timezone.now().date()
        prazo_alerta = hoje + timedelta(days=30)
        
        if proximo_lote.validade < hoje:
            # Corrigido: passamos "VENCIDO" como argumento
            return format_html(
                '<span style="background:red; color:white; padding:3px; border-radius:3px; font-weight:bold;">{}</span>', 
                "VENCIDO"
            )
        elif proximo_lote.validade <= prazo_alerta:
            dias = (proximo_lote.validade - hoje).days
            return format_html('<b style="color:orange;">FEFO: {} dias</b>', dias)
        
        # Para o caso OK, usamos a data formatada
        data_formatada = proximo_lote.validade.strftime('%d/%m/%y')
        return format_html('<span style="color:gray;">OK ({})</span>', data_formatada)
    
    status_validade.short_description = "Alerta FEFO"
    
# --- DASHBOARD FINANCEIRO DENTRO DE RECEITA EXTRA ---
@admin.register(ReceitaExtra)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'valor', 'data')

    def changelist_view(self, request, extra_context=None):
        # 1. Cálculos de Receitas
        total_vendas = Venda.objects.aggregate(Sum('valor_total'))['valor_total__sum'] or 0
        total_extras = ReceitaExtra.objects.aggregate(Sum('valor'))['valor__sum'] or 0
        
        # 2. Cálculos de Saídas
        total_despesas = Despesa.objects.aggregate(Sum('valor'))['valor__sum'] or 0
        total_compras = Compra.objects.aggregate(Sum('valor_total'))['valor_total__sum'] or 0
        
        # 3. Totais Finais
        entradas = float(total_vendas + total_extras)
        saidas = float(total_despesas + total_compras)
        lucro = entradas - saidas

        # 4. PREPARAÇÃO DOS TEXTOS (Evita o erro 'f')
        entradas_f = f"{entradas:,.2f} Kz"
        saidas_f = f"{saidas:,.2f} Kz"
        lucro_f = f"{lucro:,.2f} Kz"

        # 5. O QUADRO VISUAL
        extra_context = extra_context or {}
        extra_context['title'] = format_html(
            """
            <div style="background: #ffffff; padding: 20px; border-radius: 8px; border: 1px solid #ddd; margin-bottom: 20px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
                <h2 style="margin-top:0; color:#2c3e50; font-family: sans-serif;">📊 Resumo de Fluxo de Caixa</h2>
                <div style="display: flex; gap: 40px;">
                    <div>
                        <small style="color:gray;">TOTAL ENTRADAS</small><br>
                        <b style="color:#28a745; font-size: 18px;">{}</b>
                    </div>
                    <div>
                        <small style="color:gray;">TOTAL SAÍDAS</small><br>
                        <b style="color:#dc3545; font-size: 18px;">{}</b>
                    </div>
                    <div style="border-left: 2px solid #eee; padding-left: 40px;">
                        <small style="color:gray;">LUCRO LÍQUIDO</small><br>
                        <b style="color:#007bff; font-size: 22px;">{}</b>
                    </div>
                </div>
            </div>
            """,
            entradas_f, saidas_f, lucro_f
        )
        return super().changelist_view(request, extra_context=extra_context)
    
# REGISTOS SIMPLES (Garantir que não há duplicados aqui)
admin.site.register(Categoria)
admin.site.register(Fornecedor)
admin.site.register(Despesa)
# Note que NÃO registamos ReceitaExtra aqui no final porque já está registada acima!