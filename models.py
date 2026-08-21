from datetime import datetime
import enum
from sqlalchemy import (
    Column,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


class StatusPagamento(str, enum.Enum):
    PAGO = "pago"
    PENDENTE = "pendente"


class StatusPedido(str, enum.Enum):
    SOLICITADO = "solicitado"
    ENTREGUE = "entregue"
    CANCELADO = "cancelado"


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    telefone = Column(String(20), unique=True, nullable=False)

    pedidos = relationship("Pedido", back_populates="cliente")


class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    preco = Column(Float, nullable=False)
    quantidade_estoque = Column(Integer, default=0)
    imagem_url = Column(Text, nullable=True)  # Suporta tanto URLs normais quanto fotos em Base64


class Pedido(Base):
    __tablename__ = "pedidos"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    status_pagamento = Column(
        SqlEnum(StatusPagamento), default=StatusPagamento.PENDENTE
    )
    status_pedido = Column(
        SqlEnum(StatusPedido), default=StatusPedido.SOLICITADO
    )
    data_criacao = Column(DateTime, default=datetime.utcnow)

    cliente = relationship("Cliente", back_populates="pedidos")
    itens = relationship("ItemPedido", back_populates="pedido")


class ItemPedido(Base):
    __tablename__ = "itens_pedido"

    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    quantidade = Column(Integer, default=1)
    preco_unitario = Column(Float, nullable=False)

    pedido = relationship("Pedido", back_populates="itens")
    produto = relationship("Produto")
