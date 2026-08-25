import logging
from typing import List
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from database import Base, engine, get_db
import models
import schemas
import security

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Cria tabelas base
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    logger.error(f"Erro ao criar tabelas: {e}")


# 2. Migração segura para converter as colunas em VARCHAR(50)
def executar_migracoes_seguras():
    try:
        with engine.connect() as conn:
            if "postgresql" in str(engine.url):
                try:
                    conn.execute(text("COMMIT"))
                    conn.execute(
                        text(
                            "ALTER TABLE pedidos ALTER COLUMN status_pagamento TYPE VARCHAR(50) USING status_pagamento::text;"
                        )
                    )
                    conn.commit()
                except Exception as ex_p:
                    logger.warning(f"Aviso conversao status_pagamento: {ex_p}")

                try:
                    conn.execute(text("COMMIT"))
                    conn.execute(
                        text(
                            "ALTER TABLE pedidos ALTER COLUMN status_pedido TYPE VARCHAR(50) USING status_pedido::text;"
                        )
                    )
                    conn.commit()
                except Exception as ex_s:
                    logger.warning(f"Aviso conversao status_pedido: {ex_s}")

            inspector = inspect(engine)
            colunas_existentes = [
                col["name"] for col in inspector.get_columns("clientes")
            ]

            novas_colunas = [
                ("cpf", "VARCHAR(20)"),
                ("rg", "VARCHAR(20)"),
                ("data_nascimento", "VARCHAR(15)"),
                ("genero", "VARCHAR(20)"),
                ("estado_civil", "VARCHAR(30)"),
                ("profissao", "VARCHAR(100)"),
                ("telefone_residencial", "VARCHAR(20)"),
                ("email", "VARCHAR(100)"),
                ("instagram", "VARCHAR(100)"),
                ("endereco", "VARCHAR(255)"),
                ("numero", "VARCHAR(20)"),
                ("bairro", "VARCHAR(100)"),
                ("cidade", "VARCHAR(100)"),
                ("cep", "VARCHAR(20)"),
            ]

            for nome, tipo in novas_colunas:
                if nome not in colunas_existentes:
                    try:
                        conn.execute(
                            text(
                                f"ALTER TABLE clientes ADD COLUMN {nome} {tipo};"
                            )
                        )
                        conn.commit()
                        logger.info(f"Coluna {nome} adicionada com sucesso.")
                    except Exception as ex_col:
                        logger.warning(f"Erro ao adicionar {nome}: {ex_col}")
    except Exception as err:
        logger.error(f"Erro geral de migracao: {err}")


executar_migracoes_seguras()

app = FastAPI(
    title="Infinity 027 API",
    description="API para gestão de clientes, estoque, pedidos e crediário da Infinity 027",
    version="1.2.3",
)


@app.get("/health", tags=["Geral"])
def health_check():
    return {"status": "online"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 1. AUTENTICAÇÃO
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
# 2. CLIENTES
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
    cliente_existente = (
        db.query(models.Cliente)
        .filter(models.Cliente.telefone == dados.telefone)
        .first()
    )
    if cliente_existente:
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            if valor is not None:
                setattr(cliente_existente, campo, valor)
        db.commit()
        db.refresh(cliente_existente)
        return cliente_existente

    novo_cliente = models.Cliente(**dados.model_dump())
    db.add(novo_cliente)
    db.commit()
    db.refresh(novo_cliente)
    return novo_cliente


@app.get(
    "/clientes/telefone/{telefone}",
    response_model=schemas.ClienteResponseSchema,
    tags=["Clientes"],
)
def buscar_cliente_por_telefone(
    telefone: str,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(security.obter_usuario_logado),
):
    cliente = (
        db.query(models.Cliente)
        .filter(models.Cliente.telefone == telefone)
        .first()
    )
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return cliente


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


@app.put(
    "/produtos/{produto_id}",
    response_model=schemas.ProdutoResponseSchema,
    tags=["Produtos"],
)
def atualizar_produto(
    produto_id: int,
    dados: schemas.ProdutoCriarSchema,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(security.obter_usuario_logado),
):
    produto = (
        db.query(models.Produto)
        .filter(models.Produto.id == produto_id)
        .first()
    )
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    for campo, valor in dados.model_dump().items():
        setattr(produto, campo, valor)

    db.commit()
    db.refresh(produto)
    return produto


@app.delete("/produtos/{produto_id}", tags=["Produtos"])
def excluir_produto(
    produto_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(security.obter_usuario_logado),
):
    produto = (
        db.query(models.Produto)
        .filter(models.Produto.id == produto_id)
        .first()
    )
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    db.delete(produto)
    db.commit()
    return {"message": f"Produto '{produto.nome}' removido com sucesso."}


# ==========================================
# 4. PEDIDOS E LANÇAMENTO MANUAL DE CREDIÁRIO
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

    status_pag = (
        dados.status_pagamento.value
        if hasattr(dados.status_pagamento, "value")
        else str(dados.status_pagamento)
    ).lower()

    pedido = models.Pedido(
        cliente_id=dados.cliente_id,
        status_pagamento=status_pag,
        status_pedido="solicitado",
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


@app.post("/pedidos/manual", tags=["Crediário"])
def lancamento_manual_crediario(
    dados: schemas.LancamentoManualSchema,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(security.obter_usuario_logado),
):
    try:
        try:
            valor_float = float(str(dados.valor).replace(",", "."))
        except ValueError:
            raise HTTPException(status_code=400, detail="Valor numérico inválido.")

        # 1. Localiza ou cria o cliente
        cliente = (
            db.query(models.Cliente)
            .filter(models.Cliente.telefone == dados.telefone)
            .first()
        )
        if not cliente:
            cliente = models.Cliente(nome=dados.nome, telefone=dados.telefone)
            db.add(cliente)
            db.flush()
        elif dados.nome and cliente.nome != dados.nome:
            cliente.nome = dados.nome

        # 2. Localiza ou cria o produto avulso
        produto = (
            db.query(models.Produto)
            .filter(models.Produto.nome == dados.descricao_item)
            .first()
        )
        if not produto:
            produto = models.Produto(
                nome=dados.descricao_item,
                descricao="Lançamento manual no crediário",
                preco=valor_float,
                quantidade_estoque=999,
            )
            db.add(produto)
            db.flush()

        # 3. Cria o pedido com status fiado e entregue
        pedido = models.Pedido(
            cliente_id=cliente.id,
            status_pagamento="fiado",
            status_pedido="entregue",
        )
        db.add(pedido)
        db.flush()

        qtd = dados.quantidade if dados.quantidade and dados.quantidade > 0 else 1
        preco_unit = valor_float / float(qtd)

        item_pedido = models.ItemPedido(
            pedido_id=pedido.id,
            produto_id=produto.id,
            quantidade=qtd,
            preco_unitario=preco_unit,
        )
        db.add(item_pedido)
        db.commit()

        return {
            "message": "Débito lançado no Crediário com sucesso!",
            "pedido_id": pedido.id,
            "cliente": cliente.nome,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Erro em lancamento_manual_crediario: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao salvar débito: {str(e)}",
        )


@app.patch("/pedidos/{pedido_id}/valor", tags=["Crediário"])
def editar_valor_pedido(
    pedido_id: int,
    dados: schemas.EditarValorPedidoSchema,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(security.obter_usuario_logado),
):
    pedido = (
        db.query(models.Pedido).filter(models.Pedido.id == pedido_id).first()
    )
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    if not pedido.itens:
        raise HTTPException(
            status_code=400, detail="Pedido sem itens para alteração"
        )

    try:
        novo_valor_float = float(str(dados.novo_valor).replace(",", "."))
    except ValueError:
        raise HTTPException(status_code=400, detail="Valor numérico inválido.")

    pedido.itens[0].preco_unitario = novo_valor_float
    pedido.itens[0].quantidade = 1
    db.commit()

    return {"message": "Valor atualizado com sucesso!", "novo_valor": novo_valor_float}


@app.get(
    "/pedidos",
    response_model=List[schemas.PedidoResponseSchema],
    tags=["Pedidos"],
)
def listar_pedidos(
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(security.obter_usuario_logado),
):
    try:
        return (
            db.query(models.Pedido)
            .order_by(models.Pedido.data_criacao.desc())
            .all()
        )
    except Exception as e:
        logger.error(f"Erro em listar_pedidos: {e}")
        return []


@app.get("/fiados", tags=["Crediário"])
def listar_crediario(
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(security.obter_usuario_logado),
):
    try:
        todos_pedidos = (
            db.query(models.Pedido)
            .filter(
                models.Pedido.status_pedido != "cancelado"
            )
            .all()
        )

        pedidos_crediario = [
            p
            for p in todos_pedidos
            if str(p.status_pagamento).lower() in ["fiado", "statuspagamento.fiado"]
        ]

        clientes_crediario = {}
        for p in pedidos_crediario:
            cid = p.cliente_id
            if cid not in clientes_crediario:
                cli = p.cliente
                cliente_dados = {
                    "id": cli.id if cli else cid,
                    "nome": cli.nome if cli else f"Cliente #{cid}",
                    "telefone": cli.telefone if cli else "",
                    "cpf": getattr(cli, "cpf", None),
                    "rg": getattr(cli, "rg", None),
                    "data_nascimento": getattr(cli, "data_nascimento", None),
                    "profissao": getattr(cli, "profissao", None),
                    "instagram": getattr(cli, "instagram", None),
                    "endereco": getattr(cli, "endereco", None),
                    "numero": getattr(cli, "numero", None),
                    "bairro": getattr(cli, "bairro", None),
                    "cidade": getattr(cli, "cidade", None),
                    "cep": getattr(cli, "cep", None),
                }
                clientes_crediario[cid] = {
                    "cliente": cliente_dados,
                    "total_divida": 0.0,
                    "pedidos": [],
                }

            total_pedido = sum(
                (item.quantidade or 0) * (item.preco_unitario or 0.0)
                for item in (p.itens or [])
            )
            clientes_crediario[cid]["total_divida"] += total_pedido
            clientes_crediario[cid]["pedidos"].append(
                {
                    "pedido_id": p.id,
                    "data": (
                        p.data_criacao.strftime("%d/%m/%Y %H:%M")
                        if p.data_criacao
                        else ""
                    ),
                    "valor": total_pedido,
                    "status_pedido": str(p.status_pedido),
                    "itens": [
                        {
                            "produto": (
                                item.produto.nome
                                if item.produto
                                else f"Produto #{item.produto_id}"
                            ),
                            "quantidade": item.quantidade,
                            "preco_unitario": item.preco_unitario,
                        }
                        for item in (p.itens or [])
                    ],
                }
            )

        return list(clientes_crediario.values())
    except Exception as e:
        logger.error(f"Erro em /fiados: {e}")
        return []


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

    if str(pedido.status_pedido).lower() == "entregue":
        raise HTTPException(
            status_code=400, detail="Este pedido já foi entregue anteriormente."
        )

    for item in pedido.itens:
        if item.produto.quantidade_estoque < item.quantidade:
            raise HTTPException(
                status_code=400,
                detail=f"Estoque insuficiente para {item.produto.nome}.",
            )

    for item in pedido.itens:
        item.produto.quantidade_estoque -= item.quantidade

    pedido.status_pedido = "entregue"
    db.commit()

    return {
        "message": "Pedido entregue com sucesso.",
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

    if str(pedido.status_pedido).lower() == "cancelado":
        raise HTTPException(status_code=400, detail="Pedido já cancelado.")

    if str(pedido.status_pedido).lower() == "entregue":
        for item in pedido.itens:
            item.produto.quantidade_estoque += item.quantidade

    pedido.status_pedido = "cancelado"
    db.commit()

    return {"message": "Pedido cancelado.", "pedido_id": pedido.id}


@app.patch("/pedidos/{pedido_id}/pagamento", tags=["Pedidos"])
def atualizar_status_pagamento(
    pedido_id: int,
    dados: schemas.AtualizarPagamentoSchema,
    db: Session = Depends(get_db),
    usuario_atual: models.Usuario = Depends(security.obter_usuario_logado),
):
    pedido = (
        db.query(models.Pedido).filter(models.Pedido.id == pedido_id).first()
    )
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    status_pag = (
        dados.status_pagamento.value
        if hasattr(dados.status_pagamento, "value")
        else str(dados.status_pagamento)
    ).lower()

    pedido.status_pagamento = status_pag
    db.commit()

    return {
        "message": f"Status atualizado para {status_pag}.",
        "pedido_id": pedido.id,
        "status_pagamento": pedido.status_pagamento,
    }
