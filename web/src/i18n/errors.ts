export const ptBR = {
  network: "Sem conexão com o servidor. Tente de novo.",
  unauthorized: "Sua sessão terminou. Entre de novo.",
  invalidCredentials: "Email ou senha incorretos.",
  tooManyAttempts: "Muitas tentativas. Espere um pouco e tente de novo.",
  emailTaken: "Já existe uma conta com este email.",
  codeInvalid: "Código incorreto ou vencido.",
  invalid: "O pedido não foi aceito. Confira e tente de novo.",
  notFound: "Não encontrado: não existe ou foi para a Lixeira.",
  conflict: "Isso conflita com o que já existe.",
  server: "Erro no servidor. Tente de novo em instantes.",
  other: "Algo deu errado. Tente de novo.",
};

export const en: Record<keyof typeof ptBR, string> = {
  network: "No connection to the server. Try again.",
  unauthorized: "Your session ended. Sign in again.",
  invalidCredentials: "Wrong email or password.",
  tooManyAttempts: "Too many attempts. Wait a little and try again.",
  emailTaken: "There is already an account with this email.",
  codeInvalid: "Wrong or expired code.",
  invalid: "The request was not accepted. Check it and try again.",
  notFound: "Not found: it does not exist or went to the Trash.",
  conflict: "This conflicts with what already exists.",
  server: "Server error. Try again in a moment.",
  other: "Something went wrong. Try again.",
};
