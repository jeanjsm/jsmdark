# Instruções para GitHub Copilot

## Manutenção de código
- **NÃO** apague funções, trechos de código nem comentários existentes, a menos que explicitamente solicitado via comentário TODO ou instrução clara.
- Ao modificar funções existentes, mantenha a assinatura, tipo de retorno e documentação inalterados, a menos que solicitado.
- Se for sugerida uma função ou classe nova, NUNCA remova implementação anterior sem orientação em pull request ou issue associada.

## Estilo e padrões
- Utilize nomes de funções, variáveis e classes sempre em inglês.
- Siga PEP8 e utilize f-strings para formatação de strings.
- Docstrings de funções devem ser mantidas e, se ausentes, sugeridas no formato padrão (primeira linha descritiva no imperativo).
- Ao propor mudanças em funções de processamento de vídeo ou chamadas FFmpeg, sempre cheque se há testes associados e mantenha caso de uso compatível.
- Os imports devem ser mantidos no topo do arquivo, organizados por padrão (bibliotecas padrão, terceiros, locais) e sem duplicação.

## FFmpeg integration
- Sempre que alterar partes que usam FFmpeg (diretamente via subprocess ou wrappers), preserve exemplos e comentários explicativos.
- Não invente comandos FFmpeg: consulte sempre a documentação oficial ou scripts já no repositório.
- Garanta que todo novo comando FFmpeg adicionado esteja documentado na função correspondente.
- Evite sugerir comandos FFmpeg complexos sem verificar se já existem implementações similares no repositório.
- Se for necessário alterar a lógica de processamento de vídeo, verifique se há testes que cubram os casos de uso e mantenha-os atualizados.
- Validar o funcionamento de comandos FFmpeg com testes automatizados é essencial. Se não houver testes, crie-os para garantir a integridade do código.
- Valide o comando FFmpeg gerado com a documentação oficial do FFmpeg e com os testes existentes no repositório.

## Boas práticas gerais
- Tente sempre implementar o S.O.L.I.D. no projeto.
- Sempre preserve comentários, marcações TODO e FIXMEs.
- Não duplique funções.
- Testes automatizados não devem ser removidos nem ignorados.
- Se for necessário refatorar uma função, mantenha a lógica original antes de qualquer sugestão de alteração profunda.
- Nunca deixe funções em branco ou "stubadas" caso já haja implementação.
- Responda apenas com o código necessário para a tarefa solicitada, sem adicionar comentários desnecessários ou explicações redundantes.
- Se houver necessidade de adicionar novos testes, faça isso de forma clara e mantenha a cobertura
- Evite sugerir mudanças que não estejam diretamente relacionadas à tarefa solicitada.
- Sempre que possível, mantenha a estrutura e organização do código existente.
- Respeite a lógica de negócios existente e evite mudanças que possam quebrar funcionalidades já implementadas.
- Responda todas as solicitações de forma concisa e objetiva, focando apenas no que foi solicitado.
- Responda todas as solicitações com menos de 1000 caracteres, e em português.