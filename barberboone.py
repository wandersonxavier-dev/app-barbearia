from typing import List
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import Base, engine, get_db
import models
import schemas
import security

# 1. Cria as tabelas se não existirem
Base.metadata.create_all(bind=engine)

# 2. Inicializa a aplicação
app = FastAPI(
    title="App Barber API",
    description="API para gestão de clientes, estoque e pedidos",
    version="1.0.0",
)

# 3. Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 1. AUTENTICAÇÃO E BARBEIRO
# ==========================================


@app.post(
    "/auth/cadastro",
    response_model=schemas.UsuarioResponseSchema,
    status_code=status.HTTP_201_CREATED,
    tags=["Autenticação"],
)
def cadastrar_barbeiro(
    dados: schemas.UsuarioCriarSchema, db: Session = Depends(get_db)
):
    if (
        db.query(models.Usuario)
        .filter(models.Usuario.email == dados.email)
        .first()
    ):
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")

    novo_usuario = models.Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=security.gerar_hash_senha(dados.senha),
    )
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)
    return novo_usuario


@app.post(
    "/auth/login", response_model=schemas.TokenSchema, tags=["Autenticação"]
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    usuario = (
        db.query(models.Usuario)
        .filter(models.Usuario.email == form_data.username)
        .first()
    )
    if not usuario or not security.verificar_senha(
        form_data.password, usuario.senha_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
        )

    token = security.criar_token_acesso(dados={"sub": usuario.email})
    return {"access_token": token, "token_type": "bearer"}


# ==========================================
# 2. CLIENTES (Público para criar, Protegido para listar)
# ==========================================


@app.post(
    "/clientes",
    response_model=schemas.ClienteResponseSchema,
    status_code=status.HTTP_201_CREATED,
    tags=["Clientes"],
)
def cadastrar_ou_obter_cliente(
    dados: schemas.ClienteCriarSchema, db: Session = Depends(get_db)
):
    # Se o cliente já existir pelo telefone, atualiza o nome e retorna o existente
    cliente_existente = (
        db.query(models.Cliente)
        .filter(models.Cliente.telefone == dados.telefone)
        .first()
    )
    if cliente_existente:
        cliente_existente.nome = dados.nome
        db.commit()
        db.refresh(cliente_existente)
        return cliente_existente

    novo_cliente = models.Cliente(**dados.model_dump())
    db.add(novo_cliente)
    db.commit()
    db.refresh(novo_cliente)
    return novo_cliente


@app.get(
    "/clientes",
    response_model=List[schemas.ClienteResponseSchema],
    tags=["Clientes"],
)
def listar_clientes(
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(security.obter_usuario_logado),
):
    return db.query(models.Cliente).all()


# ==========================================
# 3. PRODUTOS E ESTOQUE
# ==========================================


@app.get(
    "/produtos/catalogo",
    response_model=List[schemas.ProdutoResponseSchema],
    tags=["Produtos"],
)
def listar_catalogo_publico(db: Session = Depends(get_db)):
    return (
        db.query(models.Produto)
        .filter(models.Produto.quantidade_estoque > 0)
        .all()
    )


@app.post(
    "/produtos",
    response_model=schemas.ProdutoResponseSchema,
    status_code=status.HTTP_201_CREATED,
    tags=["Produtos"],
)
def cadastrar_produto(
    dados: schemas.ProdutoCriarSchema,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(security.obter_usuario_logado),
):
    novo_produto = models.Produto(**dados.model_dump())
    db.add(novo_produto)
    db.commit()
    db.refresh(novo_produto)
    return novo_produto


# ==========================================
# 4. PEDIDOS E FLUXO DE ENTREGA
# ==========================================


@app.post(
    "/pedidos/publico",
    response_model=schemas.PedidoResponseSchema,
    status_code=status.HTTP_201_CREATED,
    tags=["Pedidos"],
)
def criar_pedido_web(
    dados: schemas.PedidoCriarPublicoSchema, db: Session = Depends(get_db)
):
    cliente = (
        db.query(models.Cliente)
        .filter(models.Cliente.id == dados.cliente_id)
        .first()
    )
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    pedido = models.Pedido(
        cliente_id=dados.cliente_id,
        status_pagamento=dados.status_pagamento,
        status_pedido=models.StatusPedido.SOLICITADO,
    )
    db.add(pedido)
    db.flush()

    for item in dados.itens:
        produto = (
            db.query(models.Produto)
            .filter(models.Produto.id == item.produto_id)
            .first()
        )
        if not produto:
            raise HTTPException(
                status_code=404,
                detail=f"Produto id {item.produto_id} não encontrado",
            )

        item_banco = models.ItemPedido(
            pedido_id=pedido.id,
            produto_id=produto.id,
            quantidade=item.quantidade,
            preco_unitario=produto.preco,
        )
        db.add(item_banco)

    db.commit()
    db.refresh(pedido)
    return pedido


@app.get(
    "/pedidos",
    response_model=List[schemas.PedidoResponseSchema],
    tags=["Pedidos"],
)
def listar_pedidos(
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(security.obter_usuario_logado),
):
    return (
        db.query(models.Pedido)
        .order_by(models.Pedido.data_criacao.desc())
        .all()
    )


@app.patch("/pedidos/{pedido_id}/entregar", tags=["Pedidos"])
def marcar_como_entregue(
    pedido_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(security.obter_usuario_logado),
):
    pedido = (
        db.query(models.Pedido).filter(models.Pedido.id == pedido_id).first()
    )
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    if pedido.status_pedido == models.StatusPedido.ENTREGUE:
        raise HTTPException(
            status_code=400, detail="Este pedido já foi entregue anteriormente."
        )

    for item in pedido.itens:
        if item.produto.quantidade_estoque < item.quantidade:
            raise HTTPException(
                status_code=400,
                detail=f"Estoque insuficiente para {item.produto.nome}. Disponível: {item.produto.quantidade_estoque}",
            )

    for item in pedido.itens:
        item.produto.quantidade_estoque -= item.quantidade

    pedido.status_pedido = models.StatusPedido.ENTREGUE
    db.commit()

    return {
        "message": "Pedido marcado como ENTREGUE e itens reduzidos do estoque com sucesso.",
        "pedido_id": pedido.id,
    }


@app.patch("/pedidos/{pedido_id}/cancelar", tags=["Pedidos"])
def cancelar_pedido(
    pedido_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(security.obter_usuario_logado),
):
    pedido = (
        db.query(models.Pedido).filter(models.Pedido.id == pedido_id).first()
    )
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    if pedido.status_pedido == models.StatusPedido.CANCELADO:
        raise HTTPException(
            status_code=400, detail="Este pedido já está cancelado."
        )

    # Se o pedido já havia sido entregue, devolve a quantidade para o estoque
    if pedido.status_pedido == models.StatusPedido.ENTREGUE:
        for item in pedido.itens:
            item.produto.quantidade_estoque += item.quantidade

    pedido.status_pedido = models.StatusPedido.CANCELADO
    db.commit()

    return {
        "message": "Pedido cancelado com sucesso.",
        "pedido_id": pedido.id,
    }
