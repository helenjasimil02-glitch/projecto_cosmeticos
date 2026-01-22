from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('venda/', views.registrar_venda, name='registrar_venda'),
    path('vendas/', views.lista_vendas, name='lista_vendas'), # Nova
    path('venda/<int:venda_id>/fatura/', views.ver_fatura, name='ver_fatura'), # Nova
    path('relatorios/', views.relatorios, name='relatorios'),
]