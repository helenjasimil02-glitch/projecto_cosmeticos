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
    list_display = ('nome', 'marca', 'exibir_custo_medio', 'exibir_preco_venda', 'exibir_lucro', 'exibir_stock', 'exibir_valor_inventario', 'status_validade')
    list_filter = ('categoria', 'marca')
    search_fields = ('nome', 'marca')

    # 1. Custo Médio
    def exibir_custo_medio(self, obj):
        return f"{obj.preco_custo:,.2f} Kz"
    exibir_custo_medio.short_description = "Custo Médio"

    # 2. Preço de Venda
    def exibir_preco_venda(self, obj):
        return f"{obj.preco_venda:,.2f} Kz"
    exibir_preco_venda.short_description = "Preço Venda"

    # 3. Margem de Lucro 
    def exibir_lucro(self, obj):
        lucro, perc = obj.margem_lucro()
        texto_perc = f"{perc:.1f}%"
        if perc < 15:
            return format_html('<b style="color:#ffae42;">{}</b>', texto_perc)
        return format_html('<span style="color:#58a6ff;">{}</span>', texto_perc)
    exibir_lucro.short_description = "Margem %"

    # 4. Stock Actual
    def exibir_stock(self, obj):
        texto_stock = f"{obj.stock_actual} un."
        if obj.stock_actual <= obj.stock_minimo:
            return format_html('<b style="color:#ff4d4d;">{}</b>', texto_stock)
        return texto_stock
    exibir_stock.short_description = "Stock"

    # 5. Valor Total em Stock (CORRIGIDO: O erro estava aqui!)
    def exibir_valor_inventario(self, obj):
        valor = obj.valor_total_stock()
        # Primeiro formatamos como texto puro
        valor_formatado = f"{valor:,.2f} Kz"
        # Depois enviamos para o HTML apenas como uma string '{}'
        return format_html('<b>{}</b>', valor_formatado)
    exibir_valor_inventario.short_description = "Valor Total"

    # 6. Validade (FEFO)
    def status_validade(self, obj):
        proximo_lote = obj.itemcompra_set.filter(quantidade__gt=0).order_by('validade').first()
        if not proximo_lote: return "---"
        hoje = timezone.now().date()
        prazo_alerta = hoje + timedelta(days=30)
        if proximo_lote.validade < hoje:
            return format_html('<b style="color:#ff4d4d;">{}</b>', "VENCIDO")
        elif proximo_lote.validade <= prazo_alerta:
            return format_html('<b style="color:#ffae42;">{}</b>', "FEFO")
        return proximo_lote.validade.strftime('%d/%m/%y')
    status_validade.short_description = "Validade"


# REGISTOS SIMPLES
admin.site.register(Categoria)
admin.site.register(Fornecedor)
admin.site.register(Despesa)
admin.site.register(ReceitaExtra)