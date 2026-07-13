from lpr_portaria.database import criar_tabelas

from lpr_portaria.services import (
    cadastrar_acesso_completo,
    buscar_ultimos_eventos,
)


def cadastrar_acesso():
    print("\n=== Cadastro de Acesso ===")
    nome = input("Nome: ").strip()
    email = input("Email: ").strip() or None
    tipo_cadastro = input(
        "Tipo de cadastro (morador, visitante, prestador, funcionario, empresa, entregador): "
    ).strip()

    telefone = input("Telefone: ").strip()

    placa = input("Placa do veículo: ").strip().upper()
    marca = input("Marca (opcional): ").strip() or None
    modelo = input("Modelo (opcional): ").strip() or None
    cor = input("Cor (opcional): ").strip() or None
    tipo_veiculo = input("Tipo de veículo (carro, moto, van, caminhao, utilitario): ").strip()

    resultado = cadastrar_acesso_completo(
        nome=nome,
        email=email,
        tipo_cadastro=tipo_cadastro,
        telefone=telefone,
        placa=placa,
        marca=marca,
        modelo=modelo,
        cor=cor,
        tipo_veiculo=tipo_veiculo,
    )

    print("\nCadastro realizado com sucesso!")
    print(f"Nome: {resultado['nome']}")
    print(f"Placa: {resultado['placa']}")


def mostrar_eventos():
    print("\n=== Últimos eventos ===")
    eventos = buscar_ultimos_eventos(10)

    if not eventos:
        print("Nenhum evento encontrado.")
        return

    for evento in eventos:
        print(
            f"{evento['id_evento']} | "
            f"{evento['data_hora']} | "
            f"{evento['placa_lida']} | "
            f"{evento['status']} | "
            f"{evento['nome']} | "
            f"{evento['tipo_cadastro']}"
        )


def main():
    criar_tabelas()

    while True:
        print("\n=== Admin LPR Portaria ===")
        print("1 - Cadastrar acesso")
        print("2 - Ver últimos eventos")
        print("0 - Sair")

        opcao = input("Escolha uma opção: ").strip()

        if opcao == "1":
            cadastrar_acesso()

        elif opcao == "2":
            mostrar_eventos()

        elif opcao == "0":
            print("Saindo...")
            break

        else:
            print("Opção inválida.")


if __name__ == "__main__":
    main()
