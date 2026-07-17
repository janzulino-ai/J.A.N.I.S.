# Mode B — Gate install SSD2 (970 EVO)

Dopo che l’ISO/USB TESTER è pronta, l’install sul disco hub **non** è automatica.

## Prerequisiti

- [ ] Mode A sidecar verificati (`janis doctor` non rosso) — [`SIDECARS-INSTALL.md`](SIDECARS-INSTALL.md)
- [ ] `TESTER/out/janis-tester.iso` costruita e USB di test bootabile
- [ ] Backup / conferma che il target è il **secondo** NVMe (non Windows)

## Percorso consigliato (MVP P0)

1. Boot **Debian 12 netinst** ufficiale sulla macchina target  
2. LVM su SSD2, utente `janis`, SSH  
3. NVIDIA X11 dopo primo boot  
4. Clone monorepo → [`scripts/install-server.sh`](../scripts/install-server.sh)  
5. Sidecar Mode B via `infra/sidecars/`

## Percorso TESTER (alternativo, distruttivo)

```bash
# SOLO dopo OK esplicito dell'utente
sudo bash TESTER/deploy-disk.sh /dev/nvmeXn1 --layout lvm
# digita WIPE
```

Poi first-boot NVIDIA + `install-server.sh`.

## Non fare

- Non lanciare `deploy-disk.sh` da questo sprint senza conferma  
- Non usare `--force` su `write-usb.sh` verso `sda`/`nvme0n1` senza verifica `lsblk`
