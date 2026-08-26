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


# 2. Migração segura (evita timeouts e ajusta colunas incrementalmente)
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

            # Adicionar barbearia_id nas tabelas se não existirem
            tabelas_com_barbearia = ["clientes", "produtos", "pedidos"]
            for tab in tabelas_com_barbearia:
                if tab in inspector.get_table_names():
                    cols_tab = [c["name"] for c in inspector.get_columns(tab)]
                    if "barbearia_id" not in cols_tab:
                        try:
                            conn.execute(text(f"ALTER TABLE {tab} ADD COLUMN barbearia_id INTEGER DEFAULT 1;"))
                            conn.commit()
                            logger.info(f"Coluna barbearia_id adicionada na tabela {tab}.")
                        except Exception as ex_b:
                            logger.warning(f"Erro ao adicionar barbearia_id em {tab}: {ex_b}")

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
    description="API para gestão de clientes, estoque, pedidos e crediário multi-barbearia",
    version="1.4.1",
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
def listar_catalogo_publico_geral(db: Session = Depends(get_db)):
    return (
        db.query(models.Produto)
        .filter(models.Produto.quantidade_estoque > 0)
        .all()
    )


@app.get(
    "/produtos/catalogo/{slug}",
    tags=["Produtos"],
)
def listar_catalogo_por_slug(slug: str, db: Session = Depends(get_db)):
    barbearia = db.query(models.Barbearia).filter(models.Barbearia.slug == slug).first()
    if not barbearia:
        raise HTTPException(status_code=404, detail="Barbearia não encontrada")

    produtos_db = (
        db.query(models.Produto)
        .filter(
            models.Produto.barbearia_id == barbearia.id,
            models.Produto.quantidade_estoque > 0
        )
        .all()
    )

    return {
        "barbearia_id": barbearia.id,
        "barbearia_nome": barbearia.nome,
        "produtos": produtos_db
    }


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
    barbearia = db.query(models.Barbearia).filter(models.Barbearia.usuario_id == usuario_atual.id).first()
    barbearia_id = barbearia.id if barbearia else 1

    dados_dict = dados.model_dump()
    if "barbearia_id" not in dados_dict or not dados_dict["barbearia_id"]:
        dados_dict["barbearia_id"] = barbearia_id

    novo_produto = models.Produto(**dados_dict)
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
# 4. PEDIDOS E CREDIÁRIO
# ==========================================


@app.post("/pedidos/publico", tags=["Pedidos"])
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

    barbearia_id = getattr(cliente, "barbearia_id", 1)

    pedido = models.Pedido(
        barbearia_id=barbearia_id,
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
    return {"message": "Pedido registrado com sucesso!", "id": pedido.id}


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

        barbearia = db.query(models.Barbearia).filter(models.Barbearia.usuario_id == usuario_atual.id).first()
        barbearia_id = barbearia.id if barbearia else 1

        cliente = (
            db.query(models.Cliente)
            .filter(models.Cliente.telefone == dados.telefone)
            .first()
        )
        if not cliente:
            cliente = models.Cliente(nome=dados.nome, telefone=dados.telefone, barbearia_id=barbearia_id)
            db.add(cliente)
            db.flush()
        elif dados.nome and cliente.nome != dados.nome:
            cliente.nome = dados.nome

        produto = (
            db.query(models.Produto)
            .filter(models.Produto.nome == dados.descricao_item, models.Produto.barbearia_id == barbearia_id)
            .first()
        )
        if not produto:
            produto = models.Produto(
                barbearia_id=barbearia_id,
                nome=dados.descricao_item,
                descricao="Lançamento manual no crediário",
                preco=valor_float,
                quantidade_estoque=999,
            )
            db.add(produto)
            db.flush()

        pedido = models.Pedido(
            barbearia_id=barbearia_id,
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


@app.post("/fiados/abater", tags=["Crediário"])
def abater_pagamento_crediario(
        dados: schemas.AbatimentoCrediarioSchema,
        db: Session = Depends(get_db),
        usuario_atual: models.Usuario = Depends(security.obter_usuario_logado),
):
    try:
        try:
            valor_pago = float(str(dados.valor_pago).replace(",", "."))
        except ValueError:
            raise HTTPException(status_code=400, detail="Valor de pagamento inválido.")

        if valor_pago <= 0:
            raise HTTPException(status_code=400, detail="O valor de abatimento deve ser maior que zero.")

        pedidos_cliente = (
            db.query(models.Pedido)
            .filter(
                models.Pedido.cliente_id == dados.cliente_id,
                models.Pedido.status_pedido != "cancelado"
            )
            .order_by(models.Pedido.data_criacao.asc())
            .all()
        )

        pedidos_fiados = [
            p for p in pedidos_cliente if "fiado" in str(p.status_pagamento).lower()
        ]

        if not pedidos_fiados:
            raise HTTPException(status_code=404, detail="Nenhum débito em aberto para este cliente.")

        saldo_para_abater = valor_pago

        for p in pedidos_fiados:
            if saldo_para_abater <= 0:
                break

            total_pedido = sum((it.quantidade or 0) * (it.preco_unitario or 0.0) for it in p.itens)

            if saldo_para_abater >= (total_pedido - 0.001):
                p.status_pagamento = "pago"
                saldo_para_abater -= total_pedido
            else:
                restante_pedido = total_pedido - saldo_para_abater
                if p.itens:
                    p.itens[0].preco_unitario = round(restante_pedido, 2)
                    p.itens[0].quantidade = 1
                    for item_extra in p.itens[1:]:
                        db.delete(item_extra)
                saldo_para_abater = 0.0
                break

        reg_pagamento = models.PagamentoCrediario(
            cliente_id=dados.cliente_id,
            valor_pago=valor_pago
        )
        db.add(reg_pagamento)
        db.commit()

        return {"message": "Abatimento realizado com sucesso!", "valor_abatido": valor_pago}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Erro em abater_pagamento_crediario: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao processar abatimento: {str(e)}")


@app.patch("/pedidos/{pedido_id}/mover-crediario", tags=["Crediário"])
def mover_pedido_para_crediario(
        pedido_id: int,
        db: Session = Depends(get_db),
        usuario_atual: models.Usuario = Depends(security.obter_usuario_logado),
):
    pedido = db.query(models.Pedido).filter(models.Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    pedido.status_pagamento = "fiado"
    if str(pedido.status_pedido).lower() != "entregue":
        for item in pedido.itens:
            if item.produto and item.produto.quantidade_estoque >= item.quantidade:
                item.produto.quantidade_estoque -= item.quantidade
        pedido.status_pedido = "entregue"

    db.commit()
    return {"message": "Pedido movido para o Crediário com sucesso!", "pedido_id": pedido.id}


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
    for item_extra in pedido.itens[1:]:
        db.delete(item_extra)
    db.commit()

    return {"message": "Valor atualizado com sucesso!", "novo_valor": novo_valor_float}


@app.get("/pedidos", tags=["Pedidos"])
def listar_pedidos(
        db: Session = Depends(get_db),
        usuario_atual: models.Usuario = Depends(security.obter_usuario_logado),
):
    try:
        barbearia = db.query(models.Barbearia).filter(models.Barbearia.usuario_id == usuario_atual.id).first()

        query = db.query(models.Pedido)
        if barbearia:
            query = query.filter(models.Pedido.barbearia_id == barbearia.id)

        pedidos_db = query.order_by(models.Pedido.data_criacao.desc()).all()

        resultado = []
        for p in pedidos_db:
            cli = p.cliente
            cliente_dict = {
                "id": cli.id if cli else p.cliente_id,
                "nome": cli.nome if cli else f"Cliente #{p.cliente_id}",
                "telefone": cli.telefone if cli else "",
                "cpf": getattr(cli, "cpf", None),
                "rg": getattr(cli, "rg", None),
                "data_nascimento": getattr(cli, "data_nascimento", None),
                "genero": getattr(cli, "genero", None),
                "estado_civil": getattr(cli, "estado_civil", None),
                "profissao": getattr(cli, "profissao", None),
                "telefone_residencial": getattr(cli, "telefone_residencial", None),
                "email": getattr(cli, "email", None),
                "instagram": getattr(cli, "instagram", None),
                "endereco": getattr(cli, "endereco", None),
                "numero": getattr(cli, "numero", None),
                "bairro": getattr(cli, "bairro", None),
                "cidade": getattr(cli, "cidade", None),
                "cep": getattr(cli, "cep", None),
            } if cli else None

            itens_list = []
            for item in (p.itens or []):
                prod = item.produto
                itens_list.append({
                    "id": item.id,
                    "produto_id": item.produto_id,
                    "quantidade": item.quantidade,
                    "preco_unitario": item.preco_unitario,
                    "produto": {
                        "id": prod.id if prod else item.produto_id,
                        "nome": prod.nome if prod else f"Produto #{item.produto_id}",
                        "descricao": prod.descricao if prod else None,
                        "preco": prod.preco if prod else item.preco_unitario,
                        "quantidade_estoque": prod.quantidade_estoque if prod else 0,
                        "imagem_url": prod.imagem_url if prod else None,
                    } if prod else None
                })

            resultado.append({
                "id": p.id,
                "cliente_id": p.cliente_id,
                "barbearia_id": getattr(p, "barbearia_id", 1),
                "cliente": cliente_dict,
                "status_pagamento": str(p.status_pagamento).lower(),
                "status_pedido": str(p.status_pedido).lower(),
                "data_criacao": p.data_criacao.isoformat() if p.data_criacao else None,
                "itens": itens_list,
            })

        return resultado
    except Exception as e:
        logger.error(f"Erro em listar_pedidos: {e}", exc_info=True)
        return []


@app.get("/fiados", tags=["Crediário"])
def listar_crediario(
        db: Session = Depends(get_db),
        usuario_atual: models.Usuario = Depends(security.obter_usuario_logado),
):
    try:
        barbearia = db.query(models.Barbearia).filter(models.Barbearia.usuario_id == usuario_atual.id).first()
        query = db.query(models.Pedido)
        if barbearia:
            query = query.filter(models.Pedido.barbearia_id == barbearia.id)

        todos_pedidos = query.order_by(models.Pedido.data_criacao.asc()).all()

        pedidos_crediario = [
            p
            for p in todos_pedidos
            if "fiado" in str(p.status_pagamento).lower()
               and str(p.status_pedido).lower() != "cancelado"
        ]

        total_a_receber = 0.0
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
            total_a_receber += total_pedido

            data_str = p.data_criacao.strftime("%d/%m/%Y %H:%M") if p.data_criacao else ""

            clientes_crediario[cid]["pedidos"].append(
                {
                    "pedido_id": p.id,
                    "data": data_str,
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

        todos_pagamentos = db.query(models.PagamentoCrediario).all()
        total_ja_recebido = sum(pag.valor_pago for pag in todos_pagamentos)

        return {
            "total_a_receber": total_a_receber,
            "total_ja_recebido": total_ja_recebido,
            "devedores": list(clientes_crediario.values())
        }
    except Exception as e:
        logger.error(f"Erro em /fiados: {e}", exc_info=True)
        return {"total_a_receber": 0.0, "total_ja_recebido": 0.0, "devedores": []}


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
        if item.produto and item.produto.quantidade_estoque < item.quantidade:
            raise HTTPException(
                status_code=400,
                detail=f"Estoque insuficiente para {item.produto.nome}.",
            )

    for item in pedido.itens:
        if item.produto:
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
            if item.produto:
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

    status_anterior = str(pedido.status_pagamento).lower()
    pedido.status_pagamento = status_pag

    if status_anterior == "fiado" and status_pag == "pago":
        total_pago = sum((it.quantidade or 0) * (it.preco_unitario or 0.0) for it in pedido.itens)
        reg_pagamento = models.PagamentoCrediario(
            cliente_id=pedido.cliente_id,
            pedido_id=pedido.id,
            valor_pago=total_pago
        )
        db.add(reg_pagamento)

    db.commit()

    return {
        "message": f"Status atualizado para {status_pag}.",
        "pedido_id": pedido.id,
        "status_pagamento": pedido.status_pagamento,
    }
