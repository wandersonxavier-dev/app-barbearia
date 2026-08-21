from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr

from models import StatusPagamento, StatusPedido


# --- Schemas de Autenticação / Usuário ---
class UsuarioCriarSchema(BaseModel):
    nome: str
    email: EmailStr
    senha: str


class UsuarioResponseSchema(BaseModel):
    id: int
    nome: str
    email: EmailStr

    class Config:
        from_attributes = True


class TokenSchema(BaseModel):
    access_token: str
    token_type: str


# --- Schemas de Clientes ---
class ClienteCriarSchema(BaseModel):
    nome: str
    telefone: str


class ClienteResponseSchema(ClienteCriarSchema):
    id: int

    class Config:
        from_attributes = True


# --- Schemas de Produtos ---
class ProdutoCriarSchema(BaseModel):
    nome: str
    preco: float
    quantidade_estoque: int


class ProdutoResponseSchema(ProdutoCriarSchema):
    id: int

    class Config:
        from_attributes = True


# --- Schemas de Pedidos ---
class ItemPedidoCriarSchema(BaseModel):
    produto_id: int
    quantidade: int


class ItemPedidoResponseSchema(BaseModel):
    id: int
    produto_id: int
    quantidade: int
    preco_unitario: float
    produto: Optional[ProdutoResponseSchema] = None  # <-- Adicionado para trazer o nome do produto

    class Config:
        from_attributes = True


class PedidoCriarPublicoSchema(BaseModel):
    cliente_id: int
    status_pagamento: StatusPagamento
    itens: List[ItemPedidoCriarSchema]


class PedidoResponseSchema(BaseModel):
    id: int
    cliente_id: int
    cliente: Optional[ClienteResponseSchema] = None  # <-- Adicionado para trazer nome e telefone do cliente
    status_pagamento: StatusPagamento
    status_pedido: StatusPedido
    data_criacao: datetime
    itens: List[ItemPedidoResponseSchema]

    class Config:
        from_attributes = True