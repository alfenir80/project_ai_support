# Roadmap para Tornar o Projeto Vendável (SaaS)

Para transformar este projeto de uma prova de conceito (PoC) local em um produto comercializável (SaaS - Software as a Service), várias camadas de segurança, infraestrutura e experiência do usuário precisam ser adicionadas. Abaixo está a lista detalhada do que falta no projeto atual.

## 1. Autenticação e Gestão de Usuários
Atualmente, qualquer pessoa que acesse a aplicação pode enviar um arquivo e fazer perguntas, usando uma sessão temporária baseada no `localStorage` do navegador.
* **O que falta:**
  * Sistema de Login e Cadastro (ex: email/senha, Google, GitHub).
  * Geração e validação de Tokens JWT no backend.
  * Tela de perfil do usuário.
  * Vinculação dos documentos enviados e histórico de conversas a um usuário real no banco de dados.

## 2. Banco de Dados e Armazenamento (Storage)
Os dados atualmente ficam apenas na memória do servidor ou em um banco vetorial local por sessão, que se perde ou consome muita memória com o tempo.
* **O que falta:**
  * **Banco de Dados Relacional:** (ex: PostgreSQL) para armazenar os dados dos usuários, informações de assinaturas e o registro de quais documentos eles subiram.
  * **Armazenamento de Arquivos (Object Storage):** Armazenar os PDFs fisicamente em um serviço como AWS S3 ou Google Cloud Storage em vez de processá-los apenas em memória, permitindo que o usuário acesse seus documentos depois.
  * **Persistência Vetorial Definitiva:** Usar o ChromaDB (ou Pinecone/Weaviate) associado ao ID do usuário/documento, para não precisar reprocessar o PDF toda vez que a página recarregar.

## 3. Monetização e Controle de Cotas (Billing)
Para ser vendável, você precisa cobrar pelo uso, já que a API da OpenAI tem custos por requisição/token.
* **O que falta:**
  * Integração com Gateway de Pagamento (Stripe, Mercado Pago, Pagar.me).
  * Definição de planos (ex: Grátis, Pro, Enterprise).
  * Controle de uso (Rate Limiting): Limitar quantas páginas o usuário pode processar ou quantas perguntas pode fazer dependendo do plano dele.

## 4. UI/UX Profissional e Dashboard
O design atual com Bootstrap atende bem a testes, mas para um produto comercial (SaaS), o visual precisa transmitir confiança e ser "premium".
* **O que falta:**
  * **Landing Page:** Uma página inicial vendendo o seu produto (features, preços, depoimentos).
  * **Dashboard do Usuário:** Uma área logada onde ele vê os documentos já enviados, o histórico de chats salvos, e configurações de conta.
  * **Feedback Visual Aprimorado:** Animações modernas, esqueletos de carregamento (skeletons), e design mais sofisticado, melhorando a experiência de upload e conversação.

## 5. Infraestrutura, Deploy e Segurança
O projeto atualmente roda localmente (`localhost:8000`).
* **O que falta:**
  * **Containerização:** Criar arquivos `Dockerfile` e `docker-compose.yml` para facilitar a implantação em qualquer servidor.
  * **Hospedagem (Cloud):** Subir o frontend (ex: Vercel, Netlify) e o backend (ex: Render, AWS ECS, DigitalOcean, Heroku).
  * **Domínio e SSL:** Configurar um domínio próprio (ex: `seuapp.com.br`) com certificado de segurança (HTTPS).
  * **Segurança na API:** Limitar o tamanho máximo de upload do PDF (ex: max 10MB) no backend para evitar travamentos ou custos excessivos com a OpenAI.

---

## 🚀 Próximos Passos Sugeridos

Se você quiser começar a transformar isso num produto comercial **agora mesmo**, eu recomendo esta ordem de prioridade:

1. **Refatoração Visual (UI/UX) Premium:** Melhorar o visual do frontend (Landing Page e um layout de Dashboard mais avançado, abandonando o padrão Bootstrap básico).
2. **Autenticação de Usuários:** Adicionar Login/Registro (ex: JWT no FastAPI + Context no React).
3. **Persistência de Dados (Banco):** Conectar um banco de dados SQLite (para começar) ou PostgreSQL para salvar usuários e associar arquivos/históricos a eles.
4. **Deploy:** Colocar a aplicação no ar para que outras pessoas já possam acessar e testar pela internet.
5. **Integração de Pagamentos:** Integrar o Stripe ou Mercado Pago para planos.
