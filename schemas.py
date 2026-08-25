from datetime import datetime
from typing import List, Optional, Union
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
    cpf: Optional[str] = None
    rg: Optional[str] = None
    data_nascimento: Optional[str] = None
    genero: Optional[str] = None
    estado_civil: Optional[str] = None
    profissao: Optional[str] = None
    telefone_residencial: Optional[str] = None
    email: Optional[str] = None
    instagram: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    bairro: Optional[str] = None
    cidade: Optional[str] = None
    cep: Optional[str] = None


class ClienteResponseSchema(ClienteCriarSchema):
    id: int

    class Config:
        from_attributes = True


# --- Schemas de Produtos ---
class ProdutoCriarSchema(BaseModel):
    nome: str
    descricao: Optional[str] = None
    preco: float
    quantidade_estoque: int
    imagem_url: Optional[str] = None


class ProdutoResponseSchema(ProdutoCriarSchema):
    id: int

    class Config:
        from_attributes = True


# --- Schemas de Pedidos & Itens ---
class ItemPedidoCriarSchema(BaseModel):
    produto_id: int
    quantidade: int


class ItemPedidoResponseSchema(BaseModel):
    id: int
    produto_id: int
    quantidade: int
    preco_unitario: float
    produto: Optional[ProdutoResponseSchema] = None

    class Config:
        from_attributes = True


class PedidoCriarPublicoSchema(BaseModel):
    cliente_id: int
    status_pagamento: Union[StatusPagamento, str] = "pendente"
    itens: List[ItemPedidoCriarSchema]


# --- Schemas para o Módulo de Crediário ---
class LancamentoManualSchema(BaseModel):
    telefone: str
    nome: str
    descricao_item: str
    valor: Union[float, str]
    quantidade: Optional[int] = 1


class AbatimentoCrediarioSchema(BaseModel):
    cliente_id: int
    valor_pago: Union[float, str]


class EditarValorPedidoSchema(BaseModel):
    novo_valor: Union[float, str]


class PedidoResponseSchema(BaseModel):
    id: int
    cliente_id: int
    cliente: Optional[ClienteResponseSchema] = None
    status_pagamento: str
    status_pedido: str
    data_criacao: Optional[datetime] = None
    itens: List[ItemPedidoResponseSchema] = []

    class Config:
        from_attributes = True


class AtualizarPagamentoSchema(BaseModel):
    status_pagamento: Union[StatusPagamento, str]
