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


class Barbearia(Base):
    __tablename__ = "barbearias"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", backref="barbearias", lazy="joined")
    produtos = relationship("Produto", back_populates="barbearia", lazy="selectin")
    clientes = relationship("Cliente", back_populates="barbearia", lazy="selectin")
    pedidos = relationship("Pedido", back_populates="barbearia", lazy="selectin")


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    barbearia_id = Column(Integer, ForeignKey("barbearias.id"), nullable=False, default=1)
    nome = Column(String(100), nullable=False)
    telefone = Column(String(20), index=True, nullable=False)
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

    barbearia = relationship("Barbearia", back_populates="clientes", lazy="joined")
    pedidos = relationship("Pedido", back_populates="cliente", lazy="selectin")
    pagamentos_crediario = relationship("PagamentoCrediario", back_populates="cliente", lazy="selectin")


class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    barbearia_id = Column(Integer, ForeignKey("barbearias.id"), nullable=False, default=1)
    nome = Column(String(100), nullable=False)
    descricao = Column(Text, nullable=True)
    preco = Column(Float, nullable=False)
    quantidade_estoque = Column(Integer, nullable=False, default=0)
    imagem_url = Column(Text, nullable=True)

    barbearia = relationship("Barbearia", back_populates="produtos", lazy="joined")
    itens_pedido = relationship("ItemPedido", back_populates="produto", lazy="selectin")


class Pedido(Base):
    __tablename__ = "pedidos"

    id = Column(Integer, primary_key=True, index=True)
    barbearia_id = Column(Integer, ForeignKey("barbearias.id"), nullable=False, default=1)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    status_pagamento = Column(String(50), default="pendente", nullable=False)
    status_pedido = Column(String(50), default="solicitado", nullable=False)
    data_criacao = Column(
        DateTime(timezone=True), server_default=func.now()
    )

    barbearia = relationship("Barbearia", back_populates="pedidos", lazy="joined")
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


class PagamentoCrediario(Base):
    __tablename__ = "pagamentos_crediario"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    pedido_id = Column(Integer, nullable=True)
    valor_pago = Column(Float, nullable=False)
    data_pagamento = Column(DateTime(timezone=True), server_default=func.now())

    cliente = relationship("Cliente", back_populates="pagamentos_crediario")
