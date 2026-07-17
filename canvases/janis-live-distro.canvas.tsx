import {
  Card,
  CardBody,
  CardHeader,
  Callout,
  Divider,
  Grid,
  H1,
  H2,
  H3,
  Pill,
  Row,
  Spacer,
  Stack,
  Stat,
  Table,
  Text,
  TodoList,
} from "cursor/canvas";

/**
 * JANIS Live Distro — piano prodotto / boot / ISO matrix
 * Apri in Cursor Agents Window → Canvas
 *
 * Spec dettagliata: docs/LIVE-DISTRO.md
 * GRUB assets: infra/grub/README.md
 */

const RAM_MIN_GB = 16;
const RAM_REC_GB = 32;
const USB_GB = 32;

export default function JanisLiveDistroCanvas() {
  return (
    <Stack gap={20} style={{ padding: 20, maxWidth: 1100 }}>
      <Stack gap={6}>
        <H1>JANIS Live Distro</H1>
        <Text tone="secondary">
          USB {USB_GB} GB · RAM min {RAM_MIN_GB} GB · consigliati {RAM_REC_GB} GB · fino a 4
          ISO/funzioni
        </Text>
        <Row gap={8} wrap>
          <Pill tone="success">Fattibile</Pill>
          <Pill tone="warning">Neuroni post-GRUB</Pill>
          <Pill>SSD2 wipe gated</Pill>
        </Row>
      </Stack>

      <Callout tone="warning" title="Vincolo GRUB">
        GRUB = grafica statica (PNG + theme). L’animazione neuroni Three.js parte dopo il kernel,
        in splash → kiosk Chromium (/server). Non promettere neuroni dentro il menu GRUB.
      </Callout>

      <Grid columns={4} gap={12}>
        <Stat value={`${RAM_MIN_GB} GB`} label="RAM minimo" />
        <Stat value={`${RAM_REC_GB} GB`} label="RAM consigliati" />
        <Stat value={`${USB_GB} GB`} label="USB target" />
        <Stat value="4" label="ISO / funzioni max" />
      </Grid>

      <Divider />

      <H2>1 · Media kit</H2>
      <Grid columns={2} gap={12}>
        <Card>
          <CardHeader>GRUB = master background</CardHeader>
          <CardBody>
            <Stack gap={6}>
              <Text>background.png 1920×1080 = base di TUTTO il sistema</Text>
              <Text>Menu = finestra sovrapposta (boot_menu ~40% destra)</Text>
              <Text>Stesso pattern: splash/wizard/HUD = base + overlay</Text>
              <Text tone="secondary">theme.txt + cornice nel PNG — non menu full-bleed</Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>HUD moodboard</CardHeader>
          <CardBody>
            <Stack gap={6}>
              <Text>Riferimento: Adobe Stock «futuristic HUD»</Text>
              <Text>Tema runtime: janis-theme.css (sci-fi)</Text>
              <Text>Neuroni: janis-neurons.js / JanisBrain</Text>
              <Text>Badge RAM 16 / 32 in splash e wizard</Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <Divider />

      <H2>2 · Boot chain</H2>
      <Table
        headers={["Fase", "UI", "Tech", "Note"]}
        rows={[
          [
            "GRUB",
            "Master BG + menu finestra overlay",
            "theme.txt boot_menu + background.png",
            "No Three.js",
          ],
          [
            "Kernel + live-boot",
            "Plymouth / quiet splash",
            "live-boot + initrd",
            "Monta squashfs",
          ],
          [
            "Splash neuroni",
            "Brain che si forma fullscreen",
            "Chromium kiosk → /server?phase=boot",
            "Prima superficie scenografica",
          ],
          [
            "Setup / chat",
            "Mini chat+voce + HUD risorse",
            "brain :8001 + panel overlay",
            "Wizard install assistito",
          ],
        ]}
      />

      <Divider />

      <H2>3 · Setup wizard scenografico</H2>
      <Grid columns={2} gap={12}>
        <Card>
          <CardHeader>Superficie</CardHeader>
          <CardBody>
            <Stack gap={6}>
              <Text>Sfondo: risorse CPU/RAM/disco/GPU/rete che si accendono per step</Text>
              <Text>Primo piano: mini chat + mic (STT/TTS)</Text>
              <Text>Overlay: rete, utente, driver, conferma WIPE (solo se richiesto)</Text>
              <Text tone="secondary">Pattern: janis-panel.js (panel_type overlay)</Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Step tipici</CardHeader>
          <CardBody>
            <Stack gap={4}>
              <Text>1 Detect hardware → pill risorse</Text>
              <Text>2 Rete (NM) → overlay se serve</Text>
              <Text>3 Ollama + modello → progress neuroni</Text>
              <Text>4 Brain online → chat demo funzioni</Text>
              <Text>5 Opz. install SSD (gate WIPE)</Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <Divider />

      <H2>4 · ISO matrix (stick {USB_GB} GB)</H2>
      <Table
        headers={["#", "Profilo", "Dentro", "Fuori", "ISO tipica"]}
        rows={[
          [
            "1",
            "Safe / Rescue",
            "live-boot, i3, SSH, tools",
            "NVIDIA, modelli, Comfy",
            "~3–5 GB",
          ],
          [
            "2",
            "Chat-ready",
            "brain+venv, Ollama, modello piccolo, kiosk, voce",
            "Comfy, modelli grandi",
            "~8–12 GB",
          ],
          [
            "3",
            "NVIDIA Live",
            "Chat-ready + nvidia-driver blacklist nouveau",
            "Comfy pesante",
            "~10–14 GB",
          ],
          [
            "4",
            "Media / Create",
            "Comfy + checkpoint base (o pull first-boot)",
            "Tutto il resto opzionale",
            "~15–22 GB",
          ],
        ]}
      />
      <Callout tone="info" title="Distribuzione stick">
        Una funzione per stick, oppure un’unica chiavetta Ventoy con fino a 4 ISO. Non una
        mega-ISO unica da 32 GB con tutto.
      </Callout>

      <Divider />

      <H2>5 · GPU policy</H2>
      <Grid columns={3} gap={12}>
        <Card>
          <CardHeader>Safe Live</CardHeader>
          <CardBody>
            <Text>Nouveau / CPU. Boot sempre. HUD+chat senza CUDA.</Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>NVIDIA Live</CardHeader>
          <CardBody>
            <Text>ISO #3. Driver in squashfs. Test hub RTX 3080 Ti.</Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>SSD install</CardHeader>
          <CardBody>
            <Text>first-boot janis-first-boot.sh → nvidia-driver. Wipe gated.</Text>
          </CardBody>
        </Card>
      </Grid>

      <Divider />

      <H2>6 · Gate & next</H2>
      <TodoList
        todos={[
          {
            id: "live-boot",
            content: "live-boot + initrd (chiude boot=live reale)",
            status: "pending",
          },
          {
            id: "grub-png",
            content: "Asset GRUB background.png HUD 1920×1080",
            status: "pending",
          },
          {
            id: "boot-phase",
            content: "Route /server?phase=boot splash neuroni",
            status: "pending",
          },
          {
            id: "wizard",
            content: "Wizard setup chat/voce + resource HUD",
            status: "pending",
          },
          {
            id: "iso2",
            content: "Build profilo Chat-ready su host Linux",
            status: "pending",
          },
          {
            id: "wipe",
            content: "SSD2 wipe solo conferma WIPE esplicita",
            status: "pending",
          },
        ]}
      />

      <Spacer size={8} />
      <H3>Doc</H3>
      <Text>docs/LIVE-DISTRO.md · TESTER/README.md · docs/MODE-B-SSD2-GATE.md · infra/grub/README.md</Text>
    </Stack>
  );
}
