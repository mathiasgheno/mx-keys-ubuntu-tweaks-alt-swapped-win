# MX Keys: troca automática de Alt e Win no Ubuntu

Ativa a opção **“Alt is swapped with Win”** do GNOME Tweaks quando seu MX Keys está
disponível. Reverte quando você desliga o teclado ou retira o receptor Unifying.
Funciona por eventos, sem ficar verificando a conexão a cada segundo.

## Requisitos e instalação

Ubuntu **24.04 ou superior**, sessão GNOME e GNOME Tweaks instalado. Bibliotecas:
Python 3, PyGObject/Gio/GLib e GUdev; serviços: systemd do usuário e udev.
A lista completa de pacotes e limitações está no [README principal](README.md).
Não há dependências pip nem instalação automática de pacotes.

No terminal da sua sessão gráfica, **sem sudo**:

```sh
./scripts/validate.sh
./scripts/install.sh
```

Para descoberta automática, deixe o receptor conectado e o teclado ligado.
Também é possível especificar `./scripts/install.sh --device-id SERIAL`.
O serial é individual do teclado, e não o código USB do receptor.

## Funcionamento

- Teclado com `ONLINE=1`: ativa a troca.
- Teclado com `ONLINE=0`, receptor removido ou bateria HID++ ausente: reverte.
- Login e retorno da suspensão: confere o estado uma vez.
- Parada ou desinstalação: restaura a configuração de ausência do teclado.

A preferência afeta **todos os teclados da sessão**, incluindo o integrado, e
os dois lados Alt/Super. Outras opções de teclado são preservadas. O serviço
controla o grupo `altwin:` enquanto está ativo. Se a troca já estiver habilitada
na primeira instalação, ela é removida da configuração de ausência do teclado.

O serviço inicia após o login; a tela de login não é alterada. A detecção depende
dos eventos do driver. Repouso, suspensão e primeira tecla após despertar exigem
validação no seu hardware. Bluetooth direto e Bolt não foram validados.

## Administração

```sh
python3 src/mx_keys_tweaks.py status
journalctl --user -u mx-keys-ubuntu-tweaks-alt-swapped-win.service -n 50 --no-pager
./scripts/uninstall.sh
python3 -m unittest discover -s tests -v
```

Para atualizar, obtenha o código novo e execute o instalador novamente. A
configuração existente é preservada. A desinstalação mantém o repositório e
remove somente os arquivos instalados pelo projeto.

Teste ligar/desligar, retirar/reconectar o receptor, iniciar sessão com o teclado
ligado/desligado e suspender/retomar o computador. Confira também o teclado
integrado e o repouso automático do MX Keys. Veja os detalhes e caminhos de
instalação no [README principal](README.md). Licença [MIT](LICENSE).
