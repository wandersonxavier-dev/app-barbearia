from enum import Enum
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class StatusPedido(str, Enum):
    SOLICITADO = "solicitado"
    ENTREGUE = "entregue"
    CANCELADO = "cancelado"


class StatusPagamento(str, Enum):
    PENDENTE = "pendente"
    PAGO = "pago"
    FIADO = "fiado"


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
    telefone = Column(String(20), unique=True, index=True, nullable=False)
    cpf = Column(String(20), nullable=True)
    rg = Column(String(20), nullable=True)
    data_nascimento = Column(String(15), nullable=True)
    genero = Column(String(20), nullable=True)
    estado_civil = Column(String(30), nullable=True)
    profissao = Column(String(100), nullable=True)
    telefone_residencial = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    instagram = Column(String(100), nullable=True)
    endereco = Column(String(255), nullable=True)
    numero = Column(String(20), nullable=True)
    bairro = Column(String(100), nullable=True)
    cidade = Column(String(100), nullable=True)
    cep = Column(String(20), nullable=True)

    pedidos = relationship("Pedido", back_populates="cliente", lazy="selectin")


class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    descricao = Column(Text, nullable=True)
    preco = Column(Float, nullable=False)
    quantidade_estoque = Column(Integer, nullable=False, default=0)
    imagem_url = Column(Text, nullable=True)

    itens_pedido = relationship("ItemPedido", back_populates="produto", lazy="selectin")


class Pedido(Base):
    __tablename__ = "pedidos"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    status_pagamento = Column(String(50), default="pendente", nullable=False)
    status_pedido = Column(String(50), default="solicitado", nullable=False)
    data_criacao = Column(
        DateTime(timezone=True), server_default=func.now()
    )

    cliente = relationship("Cliente", back_populates="pedidos", lazy="joined")
    itens = relationship(
        "ItemPedido", back_populates="pedido", cascade="all, delete-orphan", lazy="selectin"
    )


class ItemPedido(Base):
    __tablename__ = "itens_pedido"

    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    quantidade = Column(Integer, nullable=False, default=1)
    preco_unitario = Column(Float, nullable=False)

    pedido = relationship("Pedido", back_populates="itens")
    produto = relationship("Produto", back_populates="itens_pedido", lazy="joined")
