import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useConfig } from "../api/hooks";
import { api } from "../api/client";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Badge, Card, SectionTitle } from "../components/ui/Card";

export default function SettingsPage() {
  const { data: config, error, isLoading } = useConfig();
  const qc = useQueryClient();
  const signOut = useMutation({
    mutationFn: api.signOut,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["config"] }),
  });
  return (
    <div>
      <header className="mb-8">
        <h1 className="text-3xl font-semibold">Settings</h1>
        <p className="mt-2 text-muted">Connections the app needs. Keys live in the <code className="rounded bg-surface-2 px-1">.env</code> file on this computer.</p>
      </header>
      {isLoading && <p className="text-muted" role="status">Loading...</p>}
      {error && <Alert tone="error" title="Cannot reach the server">{error.message}</Alert>}
      {config && (
        <div className="space-y-6">
          <Card>
            <SectionTitle
              title="Gemini (picks the best moments)"
              right={<Badge tone={config.gemini_key_set ? "ok" : "bad"}>{config.gemini_key_set ? "Key found" : "Key missing"}</Badge>}
            />
            <p className="text-sm text-muted">
              {config.gemini_key_set
                ? `Default model: ${config.defaults.gemini_model}`
                : "Add GEMINI_API_KEY=... to the .env file, then restart the server."}
            </p>
          </Card>

          <Card>
            <SectionTitle
              title="YouTube"
              hint="Used to upload and schedule clips."
              right={<Badge tone={config.youtube_ready ? "ok" : "warn"}>{config.youtube_ready ? "Credentials found" : "client_secret.json missing"}</Badge>}
            />
            {!config.youtube_ready && (
              <Alert tone="info" className="mb-4">Download your OAuth client file from Google Cloud and save it as <code>client_secret.json</code> next to the app (see the README).</Alert>
            )}
            <ul className="divide-y divide-line">
              {config.accounts.map((a) => (
                <li key={a.name} className="flex items-center justify-between gap-3 py-3">
                  <div>
                    <p className="font-medium">{a.name}</p>
                    <p className="text-sm text-muted">{a.signed_in ? "Signed in" : "Not signed in yet: you sign in on the first upload"}</p>
                  </div>
                  {a.signed_in && (
                    <Button size="sm" variant="secondary" loading={signOut.isPending && signOut.variables === a.name} onClick={() => signOut.mutate(a.name)}>
                      Sign out
                    </Button>
                  )}
                </li>
              ))}
            </ul>
            {signOut.isError && <Alert tone="error" className="mt-3">{signOut.error.message}</Alert>}
            <p className="mt-3 text-xs text-muted">Add more accounts with <code>YT_ACCOUNTS=main,second</code> in the .env file.</p>
          </Card>
        </div>
      )}
    </div>
  );
}
