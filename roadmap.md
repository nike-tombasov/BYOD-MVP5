# Roadmap for MVP Stage V

## Stage V — Multi-Publisher Integration Steps
Rule: Sound must work after each step
Follow ARCHITECTURE.md
Implement end-to-end (publisher + backend + listener)

### Step 1 — Single publisher, single channel
- One publisher
- One channel
- One listener

Flow:
- publisher publish channel_0
- backend owner assign
- listener selective subscribe channel_0

Expected:
- stable audio
- listener can stop channel and play again
- listener can connect and play after channel publishing 

### Step 2 — Multi-publisher interlock
- Two publishers
- One channel

Flow:
- Publisher A ON AIR
- Publisher B tries ON AIR

Expected:
- publisher B blocked
- listener hears publisher A only

### Step 3 — Publisher switching
- Two publishers
- One channel

Flow:
- Publisher A ON AIR
- Publisher A STOP
- Publisher B ON AIR

Expected:
- listener auto switches
- no manual reconnect

### Step 4 — Multi-channel single publisher
- One publisher
- Three channels
- One listener

Publisher streams:
- channel_0
- channel_1
- channel_2

Flow:
Listener switches channels

Expected:
- correct selective subscribe
- no cross audio

### Step 5 — Multi-channel multi-publisher
Two publishers
Three channels

Publisher A → channel_0
Publisher B → channel_1
Publisher A → channel_2

Expected:
parallel streaming
listener switches freely

### Step 6 — Multi-publisher switching multi-channel
Three publishers
Three channels

Switch owners dynamically

Expected:
listener auto recovery
no duplicate audio
no subscribe errors

### Step 7 — Stress small
Three publishers
Three channels
Five listeners

Expected:
stable audio
correct owner logic

### Step 8 — Scale channels
One publisher
15 channels

Expected:
all tracks publish
listener switching works

### Step 9 — Multi-publisher scale
Multiple publishers
15 channels

Expected:
interlock stable
no race conditions

### Step 10 — Full target
Multiple publishers
32 channels
Multiple listeners

Expected:
stable audio
no drift
no duplicate tracks

## Stage V complete when:
- 3 channels multi publisher works
- switching stable
- scaling to 32 channels works without logic changes
