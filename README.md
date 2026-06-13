LPR Portaria Inteligente

Sistema de reconhecimento automático de placas veiculares desenvolvido em Python, com foco em automação de controle de acesso.

Objetivo

O projeto tem como objetivo detectar placas de veículos em tempo real, aplicar processamento de imagem, realizar leitura via OCR e registrar os acessos identificados.

Tecnologias utilizadas
Python
OpenCV
NumPy
Tesseract OCR
Git e GitHub
SQLite em desenvolvimento
Funcionalidades atuais
Captura de imagem via câmera
Detecção de regiões semelhantes a placas
Correção de perspectiva com warp
Pré-processamento da imagem para OCR
Leitura de placas com Tesseract
Validação de placas Mercosul e antigas
Registro de leituras em CSV
Estrutura modular do projeto
Estrutura do projeto
src/lpr_portaria/
├── main.py
├── camera.py
├── ocr.py
├── validacao.py
├── warp.py
├── storage.py
└── __init__.py
Próximas melhorias
Migração de CSV para SQLite
Cadastro de veículos autorizados
Consulta automática de placas no banco
Histórico de acessos
Interface gráfica
Integração futura com YOLO e PaddleOCR
Status

Projeto em desenvolvimento ativo.

Autor

Eduardo Rodrigues
Estudante de Análise e Desenvolvimento de Sistemas
Foco em Python, automação, visão computacional e banco de dados.