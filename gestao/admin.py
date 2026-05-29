from django.contrib import admin
from django.utils import timezone
from datetime import timedelta
from django.utils.html import format_html
from django.core.exceptions import ValidationError
from .models import Produto, Venda, Compra, ItemVenda, ItemCompra, Fornecedor, Despesa, ReceitaExtra, Categoria

# Admin personalizado
admin.site.site_header = "Universo de Beleza"
admin.site.site_title = "Universo de Beleza"
admin.site.index_title = "Painel de Gestão"

class ItemCompraInline(admin.TabularInline):
    model = ItemCompra
    extra = 1

class ItemVendaInline(admin.TabularInline):
    model = ItemVenda
    extra = 1

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        class ValidatedFormset(formset):
            def clean(self):
                super().clean()
                for form in self.forms:
                    if form.cleaned_data and not form.cleaned_data.get('DELETE'):
                        produto = form.cleaned_data.get('produto')
                        quantidade = form.cleaned_data.get('quantidade', 0)
                        if produto and quantidade:
                            if produto.stock_actual < quantidade:
                                raise ValidationError(
                                    f"Stock insuficiente para '{produto.nome}': "
                                    f"disponível {produto.stock_actual} un., pedido {quantidade} un."
                                )
        return ValidatedFormset

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
    search_fields = ('nome', 'marca')

    def get_readonly_fields(self, request, obj=None):
        # Depois de criado e com custo, o preço de custo fica só leitura
        if obj and obj.preco_custo > 0:
            return ('preco_custo',)
        return ()

    def exibir_custo_medio(self, obj):
        return f"{obj.preco_custo:,.2f} Kz"
    exibir_custo_medio.short_description = "Custo Médio"

    def exibir_preco_venda(self, obj):
        return f"{obj.preco_venda:,.2f} Kz"
    exibir_preco_venda.short_description = "Preço Venda"

    def exibir_lucro(self, obj):
        lucro, perc = obj.margem_lucro()
        texto_perc = f"{perc:.1f}%"
        if perc < 15:
            return format_html('<b style="color:#ffae42;">{}</b>', texto_perc)
        return format_html('<span style="color:#58a6ff;">{}</span>', texto_perc)
    exibir_lucro.short_description = "Margem %"

    def exibir_stock(self, obj):
        texto_stock = f"{obj.stock_actual} un."
        if obj.stock_actual <= obj.stock_minimo:
            return format_html('<b style="color:#ff4d4d;">{}</b>', texto_stock)
        return texto_stock
    exibir_stock.short_description = "Stock"

    def exibir_valor_inventario(self, obj):
        valor = obj.valor_total_stock()
        valor_formatado = f"{valor:,.2f} Kz"
        return format_html('<b>{}</b>', valor_formatado)
    exibir_valor_inventario.short_description = "Valor Total"

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