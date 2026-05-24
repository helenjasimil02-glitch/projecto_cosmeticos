from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    path('venda/', views.registrar_venda, name='registrar_venda'),
    path('vendas/', views.lista_vendas, name='lista_vendas'),
    path('venda/<int:venda_id>/fatura/', views.ver_fatura, name='ver_fatura'),
    path('relatorios/', views.relatorios, name='relatorios'),
    path('extrato/', views.extrato_caixa, name='extrato_caixa'),

    path('produtos/', views.lista_produtos, name='lista_produtos'),
    path('planeamento/', views.planeamento_compras, name='planeamento_compras'),
    path('fornecedores/', views.lista_fornecedores, name='lista_fornecedores'),
    path('fornecedores/novo/', views.add_fornecedor, name='add_fornecedor'),
    path('despesas/nova/', views.add_despesa, name='add_despesa'),
    path('receitas/nova/', views.add_receita, name='add_receita'),
    path('produtos/novo/', views.add_produto, name='add_produto'),
    path('produtos/<int:produto_id>/editar/', views.editar_produto, name='editar_produto'),
    path('compras/nova/', views.add_compra, name='add_compra'),
    path('planeamento/ajuste/', views.ajuste_stock, name='ajuste_stock'),
    path('compras/', views.lista_compras, name='lista_compras'),
    ]