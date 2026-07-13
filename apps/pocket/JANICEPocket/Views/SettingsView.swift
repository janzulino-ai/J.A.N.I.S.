import SwiftUI

struct SettingsView: View {
    @AppStorage("janiceServerURL") private var serverURL = ""
    @AppStorage("janiceVPNServerURL") private var vpnServerURL = ""
    @AppStorage("janicePreferVPNServer") private var preferVPN = false
    @AppStorage("janicePreferOnDeviceSTT") private var preferOnDeviceSTT = true
    @AppStorage("janiceRequireBiometric") private var requireBiometric = true
    @AppStorage("janiceBackgroundLocation") private var backgroundLocation = false
    @AppStorage("janiceSpeakResponses") private var speakResponses = false
    @AppStorage("janiceCalendarEnabled") private var calendarEnabled = false
    @AppStorage("janiceContactsEnabled") private var contactsEnabled = false
    @AppStorage("janiceLiveActivityEnabled") private var liveActivityEnabled = true

    @State private var wgServerKey = ""
    @State private var wgEndpoint = "vpn.casa.tu:51820"
    @State private var wgClientKey = ""
    @State private var showVPNConfig = false

    @ObservedObject private var identity = UserIdentityService.shared
    @ObservedObject private var stt = PocketTranscriptionService.shared
    @ObservedObject private var liveActivity = JaniceLiveActivityService.shared
    @ObservedObject private var push = JanicePushService.shared
    @ObservedObject private var calendar = JaniceCalendarService.shared
    @ObservedObject private var contacts = JaniceContactsService.shared
    @ObservedObject private var health = HealthKitService.shared
    @ObservedObject private var network = NetworkMonitorService.shared
    @ObservedObject private var sensors = JaniceSensorHub.shared

    @State private var ownerName = ""
    @State private var deviceToken = ""
    @State private var statusMessage = ""
    @State private var serverReachable = false
    @State private var isTesting = false
    @FocusState private var focusedField: Field?

    private enum Field: Hashable {
        case server, vpn, token, owner
    }

    var body: some View {
        NavigationStack {
            Form {
                identitySection
                serverSection
                vpnSection
                sttSection
                extensionsSection
                sensorsSection
                infoSection

                if !statusMessage.isEmpty {
                    Section {
                        Text(statusMessage)
                            .font(.footnote)
                            .foregroundStyle(JaniceColors.inkSoft)
                            .textSelection(.enabled)
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .navigationTitle("Impostazioni")
            .eInkScreen()
            .onAppear { loadStored() }
        }
    }

    // MARK: - Sections

    private var identitySection: some View {
        Section {
            TextField("Il tuo nome", text: $ownerName)
                .focused($focusedField, equals: .owner)
                .onSubmit { saveOwnerName() }

            Toggle("Richiedi Face ID / Touch ID", isOn: $requireBiometric)
                .onChange(of: requireBiometric) { _, v in
                    identity.setRequireBiometric(v)
                }

            Button("Verifica identità ora") {
                Task {
                    let ok = await identity.authenticate()
                    statusMessage = ok ? "Riconosciuto: \(identity.displayName)" : identity.statusMessage
                }
            }

            Button("Enroll volto sul server") {
                Task {
                    let name = ownerName.isEmpty ? identity.displayName : ownerName
                    let ok = await JaniceFaceService.shared.enroll(displayName: name)
                    statusMessage = ok ? "Volto registrato su JANIS" : "Enroll fallito"
                }
            }

            Button("Verifica volto (camera → server)") {
                Task {
                    await JaniceFaceService.shared.verifySession()
                    if JaniceFaceService.shared.lastVerified {
                        statusMessage = "Volto OK: \(JaniceFaceService.shared.verifiedName ?? "")"
                    } else {
                        statusMessage = "Volto non riconosciuto"
                    }
                }
            }

            Button("SOS emergenza") {
                Task {
                    let ok = await JaniceEmergencyService.shared.triggerSOS()
                    statusMessage = ok ? "SOS inviato al brain Linux" : "SOS fallito"
                }
            }
            .foregroundStyle(.red)

            LabeledContent("Stato", value: identity.isVerified ? "Verificato" : "Non verificato")
        } header: {
            Text("Identità — JANIS ti riconosce")
        } footer: {
            Text("Il nome e la verifica biometrica vengono inviati al brain con ogni messaggio.")
        }
    }

    private var serverSection: some View {
        Section {
            TextField("Indirizzo LAN", text: $serverURL, prompt: Text("http://192.168.1.72:8001"))
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .keyboardType(.URL)
                .focused($focusedField, equals: .server)

            TextField("Indirizzo VPN (opz.)", text: $vpnServerURL, prompt: Text("http://192.168.1.72:8001"))
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .keyboardType(.URL)
                .focused($focusedField, equals: .vpn)

            Toggle("Usa server VPN", isOn: $preferVPN)

            SecureField("Token (opzionale)", text: $deviceToken)
                .focused($focusedField, equals: .token)

            LabeledContent("Rete", value: network.isConnected ? network.interfaceType : "offline")
            LabeledContent("Server", value: serverReachable ? "Online" : "Offline")

            Button("Salva e testa") {
                focusedField = nil
                Task { await saveAndTest() }
            }
            .disabled(isTesting)
        } header: {
            Text("Server JANIS")
        } footer: {
            Text("Stesso URL LAN dopo tunnel WireGuard sul router.")
        }
    }

    private var vpnSection: some View {
        Section {
            ForEach(JaniceVPNProfileService.setupSteps(lanURL: serverURL), id: \.self) { step in
                Text(step)
                    .font(.caption)
                    .foregroundStyle(JaniceColors.textSecondary)
            }
            Toggle("Mostra template WireGuard", isOn: $showVPNConfig)
            if showVPNConfig {
                TextField("Server public key", text: $wgServerKey)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                TextField("Endpoint (host:51820)", text: $wgEndpoint)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                SecureField("Client private key", text: $wgClientKey)
                Button("Copia config WireGuard") {
                    let cfg = JaniceVPNProfileService.wireGuardConfig(
                        serverPublicKey: wgServerKey,
                        serverEndpoint: wgEndpoint,
                        clientPrivateKey: wgClientKey
                    )
                    UIPasteboard.general.string = cfg
                    statusMessage = "Config WireGuard copiata."
                }
            }
            if let url = URL(string: "https://apps.apple.com/app/wireguard/id1441195209") {
                Link("Apri WireGuard su App Store", destination: url)
            }
        } header: {
            Text("VPN WireGuard — fuori casa")
        } footer: {
            Text("Dopo VPN: stesso URL LAN in Pocket. Vedi docs/WIREGUARD-VPN-SETUP.md")
        }
    }

    private var sttSection: some View {
        Section {
            Toggle("STT on-device (WhisperKit)", isOn: $preferOnDeviceSTT)
                .onChange(of: preferOnDeviceSTT) { _, v in
                    stt.setPreferOnDevice(v)
                    if v { Task { await stt.prepareModelIfNeeded() } }
                }

            Toggle("Leggi risposte ad alta voce", isOn: $speakResponses)

            LabeledContent("Modello Whisper", value: stt.modelReady ? "Pronto" : (stt.isLoadingModel ? "Caricamento…" : "Non caricato"))
            if !stt.progressMessage.isEmpty {
                Text(stt.progressMessage)
                    .font(.caption)
                    .foregroundStyle(JaniceColors.textSecondary)
            }
        } header: {
            Text("Orecchie — trascrizione vocale")
        } footer: {
            Text("WhisperKit on-device (gratis), fallback server JANIS se fallisce.")
        }
    }

    private var extensionsSection: some View {
        Section {
            Toggle("Agenda (EventKit)", isOn: $calendarEnabled)
                .onChange(of: calendarEnabled) { _, v in
                    if v { Task { await calendar.requestAccess() } }
                }
            Toggle("Rubrica (Contacts)", isOn: $contactsEnabled)
                .onChange(of: contactsEnabled) { _, v in
                    if v { Task { await contacts.requestAccess() } }
                }
            Button("Registra push token") {
                push.requestRegistration()
                Task {
                    _ = await push.registerAction()
                    statusMessage = push.isRegistered ? "Push registrato." : push.lastError
                }
            }
            LabeledContent("Push", value: push.isRegistered ? "OK" : "—")
            LabeledContent("Agenda", value: calendar.isAuthorized ? "OK" : "Off")
            LabeledContent("Rubrica", value: contacts.isAuthorized ? "OK" : "Off")
        } header: {
            Text("Estensioni JANIS")
        } footer: {
            Text("Agenda e rubrica usabili da JANIS via bridge get_calendar / search_contacts.")
        }
    }

    private var sensorsSection: some View {
        Section {
            Toggle("HealthKit passi", isOn: Binding(
                get: { health.isEnabled },
                set: { health.setEnabled($0) }
            ))

            Toggle("Posizione in background", isOn: $backgroundLocation)
                .onChange(of: backgroundLocation) { _, v in
                    sensors.setBackgroundLocationEnabled(v)
                }

            Toggle("Live Activity brain/job", isOn: $liveActivityEnabled)
                .onChange(of: liveActivityEnabled) { _, v in
                    liveActivity.setEnabled(v)
                    if v {
                        liveActivity.sync(from: BrainStateController.shared)
                    }
                }
            LabeledContent("Live Activity", value: liveActivity.isActive ? "Attiva" : "—")

            LabeledContent("Telemetry", value: sensors.lastTelemetryAt?.formatted(date: .omitted, time: .shortened) ?? "—")
            LabeledContent("Comando bridge", value: sensors.lastCommandLabel.isEmpty ? "—" : sensors.lastCommandLabel)
            LabeledContent("Coda offline", value: "\(sensors.queuedTelemetryCount)")
        } header: {
            Text("Sensori — occhi e contesto")
        }
    }

    private var infoSection: some View {
        Section {
            LabeledContent("App", value: "JANICE Pocket")
            LabeledContent("Versione", value: "3.1.0 (9)")
            LabeledContent("Device ID", value: JaniceAPIClient.deviceID)
            LabeledContent("Bundle", value: "ai.janzulino.janice.pocket")
        } header: {
            Text("Informazioni")
        }
    }

    // MARK: - Actions

    private func loadStored() {
        ownerName = identity.displayName
        if serverURL.isEmpty {
            serverURL = KeychainService.loadServerBaseURL() ?? ""
        }
        if vpnServerURL.isEmpty {
            vpnServerURL = KeychainService.loadVPNServerBaseURL() ?? ""
        }
        deviceToken = KeychainService.loadDeviceToken() ?? ""
        requireBiometric = identity.requireBiometric
    }

    private func saveOwnerName() {
        identity.setDisplayName(ownerName)
        statusMessage = "Nome salvato."
    }

    private func saveAndTest() async {
        isTesting = true
        defer { isTesting = false }

        let url = serverURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !url.isEmpty else {
            statusMessage = "Inserisci l'indirizzo del server."
            return
        }

        do {
            UserDefaults.standard.set(url, forKey: "janiceServerURL")
            try KeychainService.saveServerBaseURL(url)

            let vpn = vpnServerURL.trimmingCharacters(in: .whitespacesAndNewlines)
            if vpn.isEmpty {
                KeychainService.deleteVPNServerBaseURL()
            } else {
                UserDefaults.standard.set(vpn, forKey: "janiceVPNServerURL")
                try KeychainService.saveVPNServerBaseURL(vpn)
            }

            let tok = deviceToken.trimmingCharacters(in: .whitespacesAndNewlines)
            if tok.isEmpty {
                KeychainService.deleteDeviceToken()
            } else {
                try KeychainService.saveDeviceToken(tok)
            }

            identity.setDisplayName(ownerName)
            identity.setRequireBiometric(requireBiometric)

            serverReachable = await JaniceAPIClient.shared.ping()
            statusMessage = serverReachable
                ? "Server raggiungibile (\(preferVPN ? "VPN" : "LAN"))."
                : "Server non raggiungibile."
        } catch {
            statusMessage = "Errore: \(error.localizedDescription)"
        }
    }
}

#Preview {
    SettingsView()
}
