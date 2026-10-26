/**
 * The browser's WebAuthn calls, between the options py_webauthn sends as JSON and the credential JSON it parses back:
 * binary fields travel as base64url both ways.
 */

type Descriptor = { id: string; type: "public-key"; transports?: AuthenticatorTransport[] };
type CreationJSON = Omit<PublicKeyCredentialCreationOptions, "challenge" | "user" | "excludeCredentials"> & {
  challenge: string;
  user: { id: string; name: string; displayName: string };
  excludeCredentials?: Descriptor[];
};
type RequestJSON = Omit<PublicKeyCredentialRequestOptions, "challenge" | "allowCredentials"> & {
  challenge: string;
  allowCredentials?: Descriptor[];
};

function bytes(base64url: string): ArrayBuffer {
  return Uint8Array.from(atob(base64url.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0)).buffer;
}

function base64url(buffer: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

const descriptors = (list?: Descriptor[]) => list?.map((descriptor) => ({ ...descriptor, id: bytes(descriptor.id) }));

/** The person closed or refused the browser's prompt, or another prompt took its place: nothing to tell them. */
export function cancelled(error: unknown): boolean {
  return error instanceof DOMException && (error.name === "NotAllowedError" || error.name === "AbortError");
}

/** Whether the browser offers passkeys in the autofill of a field with `autocomplete="username webauthn"`. */
export async function autofillAvailable(): Promise<boolean> {
  return typeof PublicKeyCredential !== "undefined" && (await PublicKeyCredential.isConditionalMediationAvailable?.()) === true;
}

/** Runs the browser's prompt to create a passkey from the registration options. */
export async function createPasskey(options: Record<string, unknown>): Promise<Record<string, unknown>> {
  const json = options as unknown as CreationJSON;
  const credential = (await navigator.credentials.create({
    publicKey: {
      ...json,
      challenge: bytes(json.challenge),
      user: { ...json.user, id: bytes(json.user.id) },
      excludeCredentials: descriptors(json.excludeCredentials),
    },
  })) as PublicKeyCredential;
  const response = credential.response as AuthenticatorAttestationResponse;
  return {
    id: credential.id,
    rawId: base64url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment,
    clientExtensionResults: credential.getClientExtensionResults(),
    response: {
      clientDataJSON: base64url(response.clientDataJSON),
      attestationObject: base64url(response.attestationObject),
      transports: response.getTransports?.() ?? [],
    },
  };
}

/** Runs the browser's prompt to sign with a passkey; with `autofill`, it waits in the email field's suggestions. */
export async function getPasskey(
  options: Record<string, unknown>,
  autofill?: AbortSignal,
): Promise<Record<string, unknown>> {
  const json = options as unknown as RequestJSON;
  const credential = (await navigator.credentials.get({
    publicKey: { ...json, challenge: bytes(json.challenge), allowCredentials: descriptors(json.allowCredentials) },
    ...(autofill && { mediation: "conditional", signal: autofill }),
  })) as PublicKeyCredential;
  const response = credential.response as AuthenticatorAssertionResponse;
  return {
    id: credential.id,
    rawId: base64url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment,
    clientExtensionResults: credential.getClientExtensionResults(),
    response: {
      clientDataJSON: base64url(response.clientDataJSON),
      authenticatorData: base64url(response.authenticatorData),
      signature: base64url(response.signature),
      userHandle: response.userHandle && base64url(response.userHandle),
    },
  };
}
