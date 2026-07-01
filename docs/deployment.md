# IntentEscrow deployment prep

IntentEscrow is intended for GenLayer Studionet/Bradbury after local validation.

## Prerequisites

- `genlayer` CLI installed
- local GenLayer account created/imported
- account unlocked locally when deploying
- selected network configured: `studionet` or `testnet-bradbury`
- enough faucet/test balance if the network requires it

Never paste private keys or keystore passwords into chat. Enter them locally when the CLI prompts.

## Local validation

```bash
python3.12 -m venv .venv312
. .venv312/bin/activate
pip install pytest genvm-linter
./scripts/check.sh
```

## Network/account checks

```bash
genlayer network list
genlayer network info
genlayer account list
genlayer account show
```

## Deploy

```bash
./scripts/deploy.sh studionet
# or
./scripts/deploy.sh testnet-bradbury
```

## Post-deploy verification

```bash
genlayer receipt <TX_ID>
genlayer trace <TX_ID>
genlayer schema <CONTRACT_ADDRESS>
genlayer code <CONTRACT_ADDRESS>
```

Record:

- network
- contract address
- deploy tx id
- receipt/trace execution status
- schema methods count
- pinned runner hash
