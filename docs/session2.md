# Agent Context Yapısı — Kişisel Asistan / İkinci Beyin Mimarisi

Tarif ettiğiniz şey klasik bir “memory” sisteminden biraz daha geniş: **LLM’den bağımsız çalışan, kalıcı bir Agent Operating Context / Personal Knowledge Layer**.

En kritik tasarım kararı şu olmalı:

> **LLM hafızanın sahibi olmamalı. LLM hafızayı okuyan ve değişiklik öneren bir istemci olmalı.**
>
> Gerçek hafıza; sizin veri modelinizde, versiyonlanmış ve kaynakları belli şekilde tutulmalı.

Böylece GPT, Claude, Gemini, yerel modeller veya ileride çıkacak başka modeller arasında geçiş yaptığınızda “ikinci beyniniz” kaybolmaz.

## Önerdiğim genel mimari

```text
                         ┌──────────────────────┐
                         │      USER INPUT      │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │    AGENT RUNTIME     │
                         │ orchestration/tools  │
                         └──────────┬───────────┘
                                    │
                   ┌────────────────▼────────────────┐
                   │        CONTEXT COMPILER         │
                   │                                 │
                   │ hangi bilgileri modele          │
                   │ göndereceğine karar verir       │
                   └───────┬──────────────┬──────────┘
                           │              │
                 ┌─────────▼─────┐ ┌──────▼──────────┐
                 │ MEMORY SYSTEM │ │ RULES / PROFILE │
                 └──────┬────────┘ └─────────────────┘
                        │
        ┌───────────────┼──────────────────┐
        │               │                  │
   Session Memory   Long-term Memory   Knowledge/Sources
        │               │                  │
        └───────────────┼──────────────────┘
                        │
                  ┌─────▼──────┐
                  │ STORAGE DB │
                  │ + files    │
                  │ + vectors  │
                  └────────────┘
```

Burada LLM sadece en üstteki çalışma motorlarından biri.

---

# 1. Context'i 7 ayrı katmana ayırın

Tek bir `context.md` dosyası yapmanızı önermem.

Context'i en az şu alanlara bölün:

| Katman | Ne içerir? | Değişme sıklığı |
|---|---|---|
| `constitution` | Agent'ın değişmez kuralları | Çok düşük |
| `agent_profile` | Agent'ın rolü ve çalışma tarzı | Düşük |
| `user_profile` | Sizin hakkınızdaki bilgiler | Orta |
| `procedures` | İşlerin nasıl yapılacağı | Orta |
| `projects` | Aktif proje/task durumları | Yüksek |
| `memory` | Öğrenilmiş bilgiler/notlar | Yüksek |
| `sessions` | Konuşma ve çalışma geçmişleri | Çok yüksek |

Örneğin:

```text
context/
│
├── constitution/
│   ├── principles.yaml
│   ├── security.yaml
│   └── memory_policy.yaml
│
├── agent/
│   ├── identity.yaml
│   ├── behavior.yaml
│   └── capabilities.yaml
│
├── user/
│   ├── profile.yaml
│   ├── preferences.yaml
│   ├── people.yaml
│   └── routines.yaml
│
├── projects/
│   ├── project-001/
│   │   ├── project.yaml
│   │   ├── state.yaml
│   │   ├── decisions/
│   │   ├── notes/
│   │   └── sources/
│   └── ...
│
├── memory/
│   ├── semantic/
│   ├── episodic/
│   ├── procedures/
│   └── inbox/
│
├── sessions/
│   └── 2026/
│
└── sources/
```

Ama fiziksel olarak bunların hepsinin dosya olması gerekmiyor.

Daha sonra Postgres/SQLite üzerinde saklayabilirsiniz.

---

# 2. Hafızayı üç seviyede düşünün

Burada özellikle şu ayrım çok önemli.

## A. Raw Event

Değiştirilemez kayıt.

Örneğin:

```yaml
event_id: evt_93K2
type: user_message
session_id: ses_2039
timestamp: 2026-10-06T18:30:00+03:00

content: >
  Kullanıcı yeni CRM projesinde PostgreSQL
  kullanmak istediğini söyledi.
```

Bu kayıt **immutable** olmalı.

Sonradan değiştirilmemeli.

---

## B. Distilled Memory

Agent'ın eventlerden çıkardığı anlamlı bilgi.

```yaml
id: mem_32874

type: preference

subject: database

content: >
  Kullanıcı yeni projelerde PostgreSQL
  kullanmayı tercih ediyor.

confidence: 0.82

evidence:
  - evt_93K2

created_at: 2026-10-06T18:35:00+03:00
updated_at: 2026-10-06T18:35:00+03:00
```

Bu kayıt değişebilir.

---

## C. Current State

Agent'ın şu anda doğru kabul ettiği durum.

```yaml
database_preferences:
  primary: PostgreSQL
  avoid:
    - MongoDB

last_updated: 2026-10-06
```

Bu sayede:

```text
RAW HISTORY
    ↓
DERIVED MEMORY
    ↓
CURRENT STATE
```

oluşur.

Bu model, ileride hafızanın neden oluştuğunu anlamanızı sağlar.

---

# 3. Her notun standart bir veri modeli olsun

En önemli objeniz muhtemelen `MemoryNote` olacaktır.

Şuna benzer bir yapı tavsiye ederim:

```yaml
id: note_01JAKZ8X

schema_version: 1

type: knowledge

title: PostgreSQL tercihi

content: >
  Kullanıcı backend projelerinde PostgreSQL
  kullanmayı tercih ediyor.

scope:
  - user

tags:
  - database
  - backend
  - preference

status: active

importance: 0.75
confidence: 0.90

created_at: 2026-10-06T18:42:00+03:00
updated_at: 2026-10-06T18:42:00+03:00

created_by:
  type: agent
  model: model-x

source_refs:
  - evt_93K2

parent_id: null

children:
  - note_01JAL0Y4

relations:
  - type: related_to
    target: note_backend_stack

supersedes: null

valid_from: 2026-10-06
valid_until: null
```

Özellikle şu alanları ihmal etmeyin:

```text
id
type
scope
confidence
importance
source_refs
created_at
updated_at
parent_id
relations
supersedes
```

Bunlar ileride çok işinize yarayacak.

---

# 4. Alt notları bir tree değil, graph olarak düşünün

Sizin söylediğiniz:

> "kendi alt notlarını oluşturabilecek"

özelliği kesinlikle olmalı.

Örneğin:

```text
Ben
│
├── İş
│   ├── Şirket A
│   │   ├── İnsanlar
│   │   ├── Projeler
│   │   └── Toplantılar
│   │
│   └── Kariyer hedefleri
│
├── Kişisel
│   ├── Seyahat
│   ├── Tercihler
│   └── Hobiler
│
└── Teknik
    ├── Infrastructure
    ├── AI
    └── Software Architecture
```

Ama sadece parent-child sistemi yeterli değildir.

Çünkü aynı not:

```text
AI
↕
Project X
↕
Company A
```

ile ilişkili olabilir.

Dolayısıyla:

```yaml
parent_id:
relations:
```

ikisini birlikte kullanın.

Yani sisteminiz aslında küçük bir **knowledge graph** haline gelir.

---

# 5. Memory type'larını baştan belirleyin

Her şeyi "note" diye kaydetmek ileride karmaşa yaratır.

Ben en az şu türleri kullanırdım:

```text
fact
preference
person
organization
decision
goal
task
project
idea
knowledge
procedure
event
observation
conversation
resource
question
open_loop
```

Örneğin:

```yaml
type: decision

content: >
  Project Phoenix için backend dili olarak
  Go kullanılmasına karar verildi.
```

ve:

```yaml
type: open_loop

content: >
  Auth sistemi için provider seçimi henüz yapılmadı.
```

çok farklı anlamlara sahiptir.

Agent bunlara farklı davranabilir.

---

# 6. Session yapısı ayrı tutulmalı

Her Agent çalışması bir `session` üretmeli.

Örneğin:

```yaml
session_id: ses_20261006_001

started_at: 2026-10-06T17:12:00+03:00
ended_at: 2026-10-06T18:43:00+03:00

agent:
  id: personal-assistant

model:
  provider: provider-x
  model: model-y
  version: "2026-09"

objective: >
  Project Phoenix mimarisini incelemek

projects:
  - phoenix

sources_used:
  - src_2837
  - src_2938

memories_used:
  - mem_8237
  - mem_8328

memories_created:
  - mem_9382

memories_updated:
  - mem_2831

decisions:
  - dec_2847

open_loops:
  - loop_9283
```

Session sonunda agent otomatik olarak bir özet oluşturabilir:

```yaml
summary:
  accomplished:
    - API mimarisi belirlendi
    - PostgreSQL tercih edildi

  decisions:
    - REST kullanılacak

  follow_ups:
    - Auth provider araştırılacak

  learned:
    - Kullanıcı database migration'larında Alembic tercih ediyor.
```

Bu yapı bir sonraki oturum için çok değerlidir.

---

# 7. Session başlangıcında tüm hafızayı LLM'e vermeyin

En sık yapılan hata bu olur.

Örneğin zamanla:

```text
10.000 not
1000 session
500 kaynak
50 proje
```

olabilir.

Bunların hepsini prompt'a koyamazsınız.

Bunun yerine bir **Context Compiler** oluşturun.

---

# Context Compiler

Görevi:

```text
User prompt
     ↓
intent detection
     ↓
hangi proje?
hangi kişi?
hangi konu?
     ↓
memory retrieval
     ↓
ranking
     ↓
context compression
     ↓
LLM prompt
```

Örneğin kullanıcı:

> Phoenix projesindeki auth konusu ne olmuştu?

dediğinde compiler:

```text
constitution
+
user profile'dan gerekli minimum bilgiler
+
Phoenix project current state
+
auth ile ilgili decision'lar
+
auth ile ilgili son sessionlar
+
ilgili kaynaklar
```

getirsin.

Kullanıcının bütün hayat hikâyesini getirmesin.

---

# 8. Retrieval hybrid olmalı

Sadece vector database kullanmanızı önermem.

Şu kombinasyon çok daha iyi:

```text
Metadata filtering
+
Full text search / BM25
+
Vector similarity
+
Recency
+
Importance
+
Graph relationships
```

Örneğin scoring:

```text
score =
  0.35 semantic_similarity
+ 0.20 keyword_match
+ 0.15 importance
+ 0.15 recency
+ 0.10 relationship_strength
+ 0.05 confidence
```

Rakamlar örnek.

Daha sonra tune edebilirsiniz.

---

# 9. Model bağımsızlığı için ContextPackage kullanın

Agent doğrudan OpenAI/Anthropic/Gemini prompt'u oluşturmasın.

Arada sizin standart formatınız olsun:

```json
{
  "context_version": "1.4",

  "rules": [],

  "agent": {},

  "user": {},

  "task": {},

  "project": {},

  "memories": [],

  "sources": [],

  "session": {}
}
```

Buna örneğin:

```text
ContextPackage
```

diyebilirsiniz.

Ardından:

```text
ContextPackage
     │
 ┌───┼────────┐
 ▼   ▼        ▼
GPT Claude Gemini
 │    │        │
 ▼    ▼        ▼
Adapter Adapter Adapter
```

Her provider'ın adapter'ı aynı context'i kendi anlayacağı prompt formatına dönüştürür.

---

# 10. LLM adapter katmanı oluşturun

Örneğin:

```python
class LLMAdapter:

    def compile_context(context_package):
        ...

    def call(messages, tools):
        ...

    def parse_tool_call(response):
        ...

    def structured_output(schema):
        ...
```

Implementasyonlar:

```text
OpenAIAdapter
AnthropicAdapter
GeminiAdapter
LocalModelAdapter
```

Böylece agent kodunuz:

```python
agent.run(context)
```

der.

Modelin hangisi olduğunu önemsemez.

---

# 11. Context window modelden bağımsız yönetilmeli

Context compiler modelin kapasitesini bilmeli.

Örneğin:

```yaml
model:
  max_context_tokens: ...
  max_output_tokens: ...

context_budget:

  rules: 0.15
  user_profile: 0.10
  task_state: 0.20
  memories: 0.25
  sources: 0.20
  reserve: 0.10
```

Ama bunları sabit limit değil, guideline olarak kullanın.

Compiler gerekirse eski sessionları özetleyebilir.

---

# 12. Agent doğrudan hafızayı değiştirmemeli

Bu bence mimarinin en önemli bölümlerinden biri.

Agent:

```text
memory.update(...)
```

yapmasın.

Bunun yerine:

```text
MemoryMutationProposal
```

oluştursun.

Örneğin:

```json
{
  "operation": "update",
  "memory_id": "mem_123",

  "reason": "User corrected previous information.",

  "old_value": "User lives in Ankara",
  "new_value": "User lives in Istanbul",

  "evidence": [
    "evt_9382"
  ],

  "confidence": 0.99
}
```

Sonra memory manager:

```text
validate
↓
conflict check
↓
permissions
↓
commit
```

yapsın.

Bu sayede model yanlış bir inference yaptığında hafızanızı bozmaz.

---

# 13. "Gözlem" ile "gerçek" arasında fark koyun

Örneğin agent şunu düşünmüş olabilir:

> Kullanıcı muhtemelen Go'yu Python'dan daha fazla seviyor.

Bunu:

```yaml
type: fact
```

olarak kaydetmemelisiniz.

Şöyle:

```yaml
type: observation

confidence: 0.45

content: >
  User may prefer Go over Python based on
  recent architecture discussions.
```

olmalı.

Daha sonra yeterli kanıt oluşunca preference'a dönüştürülebilir.

---

# 14. Her memory'nin provenance'ı olmalı

"Agent bunu nereden biliyor?"

sorusuna her zaman cevap verebilmelisiniz.

Örneğin:

```text
Memory
 ↓
source_refs
 ↓
session
 ↓
message
 ↓
original content
```

Örneğin:

```yaml
source_refs:

  - type: conversation
    id: evt_2394

  - type: document
    id: src_9382

  - type: url
    id: src_2837
```

Bu ileride agent'ın:

> "Bunu 14 Ağustos'taki konuşmanızdan biliyorum."

diyebilmesini sağlar.

---

# 15. Kaynakları da first-class object yapın

Örneğin:

```yaml
id: src_029381

type: webpage

title: PostgreSQL documentation

uri: ...

captured_at: 2026-10-06

content_hash: sha256:...

snapshot:
  file: sources/029381.md
```

Bir PDF ise:

```yaml
type: pdf

original_file: architecture.pdf

content_hash: ...

extracted_text: ...

summary: ...

chunks:
  - ...
```

Böylece bilgi ile kaynak birbirinden ayrılır.

---

# 16. Memory lifecycle tanımlayın

Bir hafıza sonsuza kadar aynı şekilde kalmamalı.

Ben şu state'leri kullanırdım:

```text
candidate
↓
active
↓
superseded
↓
archived
```

veya:

```text
deleted / tombstone
```

Örneğin:

```yaml
id: pref_01

content: VS Code kullanıyor.

status: superseded

superseded_by: pref_02
```

Yeni kayıt:

```yaml
id: pref_02

content: Cursor kullanıyor.

status: active
```

Eski bilgiyi silmek yerine version history bırakmak daha doğru.

---

# 17. Personal assistant için User Profile çok önemli

User profile bir biography metni olmamalı.

Structured data daha iyi.

Örneğin:

```yaml
identity:
  name: ...

communication:
  preferred_language: tr

  style:
    concise: true
    technical_depth: high

work:
  roles: []

technical:
  preferred_languages:
    - Python
    - Go

  preferred_database:
    - PostgreSQL

preferences: []

people: []

organizations: []

goals: []

routines: []
```

Ama bunların tamamını her prompt'a vermeyin.

Context compiler sadece ilgili kısmı getirsin.

---

# 18. Project memory ayrı olmalı

Örneğin:

```text
Project: Phoenix
```

için:

```yaml
id: project_phoenix

status: active

objective: >

participants: []

current_state: >

decisions: []

tasks: []

open_questions: []

constraints: []

resources: []

related_memories: []
```

Böylece yeni session başladığında agent:

> Phoenix projesinde en son nerede kalmıştık?

sorusuna doğrudan cevap verebilir.

---

# 19. Open Loop sistemi ekleyin

"İkinci beyin" sistemlerinde çok işe yarar.

Örneğin:

```yaml
id: loop_82737

type: open_loop

title: Auth provider seçimi

project: phoenix

status: waiting

waiting_for:
  type: research

next_action:
  Compare Auth0, Clerk and Keycloak.

created_at: ...

review_after: ...
```

Böylece agent sadece bilgi tutmaz.

**Yarım kalan işleri de hatırlar.**

---

# 20. Session lifecycle

Ben runtime'ı şu şekilde tasarlardım.

### Session başladığında

```text
1. Constitution yükle
2. Agent profile yükle
3. User'ın ilgili profilini getir
4. Aktif project/task tespit et
5. İlgili memories retrieve et
6. Son alakalı sessionları getir
7. Open loop'ları getir
8. ContextPackage oluştur
9. Model adapter'a gönder
```

Session sırasında:

```text
messages → event log

tool calls → event log

decisions → memory candidate

new facts → memory candidate

new resources → source registry

task changes → project state
```

Session sonunda:

```text
Session summarization
        ↓
Facts
Decisions
Preferences
Ideas
Tasks
Open Loops
Sources
        ↓
Memory candidates
        ↓
validation
        ↓
long-term memory
```

---

# 21. Agent'ın session sonunda yapabileceği memory extraction

Örneğin structured output:

```json
{
  "summary": "...",

  "memories": [
    {
      "type": "preference",
      "content": "...",
      "confidence": 0.9
    }
  ],

  "decisions": [],

  "tasks": [],

  "open_loops": [],

  "people": [],

  "resources": []
}
```

Sonra ayrı bir Memory Manager bunları işler.

---

# 22. Çok önemli: Agent Rule ≠ Memory

Bunları asla karıştırmayın.

Örneğin:

```text
"Kullanıcı Türkçe cevapları tercih ediyor."
```

memory/profile olabilir.

Ama:

```text
"Kullanıcının özel verisini izni olmadan dış servislere gönderme."
```

memory değildir.

Bu:

```text
constitution/security rule
```

olmalıdır.

Agent kendi constitution'ını değiştirememeli.

---

# 23. Rule priority sistemi oluşturun

Örneğin:

```text
Level 0 — Security
Level 1 — Constitution
Level 2 — Agent policy
Level 3 — User permanent preferences
Level 4 — Project instructions
Level 5 — Session instructions
Level 6 — Current request
```

Çelişki olduğunda hangi talimatın kazanacağı belli olur.

---

# 24. Storage için başlangıç mimarisi

İlk versiyonda fazla karmaşıklaştırmazdım.

Şununla başlayabilirsiniz:

```text
PostgreSQL
+
pgvector
+
object storage
```

veya tamamen local:

```text
SQLite
+
FTS5
+
local embeddings/vector index
+
filesystem
```

Canonical bilgiler relational DB'de olsun.

Vector DB sadece **retrieval index** olsun.

Yani:

> Vector DB hafızanız değildir.

Asıl data:

```text
Postgres / SQLite
```

olsun.

---

# 25. Önerdiğim database modeli

Yaklaşık:

```text
users
agents

sessions
events

memories
memory_versions
memory_relations
memory_sources

projects
tasks
decisions
open_loops

sources
source_chunks

entities
entity_relations

context_snapshots
```

Çok güçlü bir temel olur.

---

# 26. Context Snapshot da kaydedin

Bu özellik özellikle farklı LLM'lerle çalışırken çok değerli.

Her inference için:

```yaml
context_snapshot:

  model: ...
  model_version: ...

  compiler_version: 3

  rules_version: 8

  memories:
    - mem_01
    - mem_02

  project_state_version: 18
```

kaydedin.

Böylece ileride:

> Model neden böyle cevap verdi?

sorusunun cevabını bulabilirsiniz.

---

# 27. Model version değişikliklerine karşı regression testleri kurun

Örneğin:

```text
TEST 1
Kullanıcı "çok kısa cevap ver" tercihine sahip.
Agent uzun cevap vermemeli.

TEST 2
Eski memory yeni bilgiyle superseded edilmiş.
Agent eski bilgiyi kullanmamalı.

TEST 3
Project A bilgileri Project B'ye sızmamalı.

TEST 4
Agent düşük confidence observation'ı fact olarak söylememeli.

TEST 5
Kaynağı olmayan önemli kişisel bilgiyi uydurmamalı.
```

Her yeni model versiyonunda aynı test suite'i çalıştırabilirsiniz.

Bu, çoklu LLM desteğinde ciddi fark yaratır.

---

# Ben olsam sistemin çekirdeğini şöyle kurardım

```text
                    PERSONAL AGENT OS
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
     Rules              Memory             State
        │                  │                  │
 Constitution       Semantic memory       Projects
 Agent Policy       Episodic memory       Tasks
 Security           User profile          Open loops
                    Procedures            Decisions
                           │
                     Knowledge Graph
                           │
                       Sources
                           │
                  Retrieval / Search
                           │
                   Context Compiler
                           │
              ┌────────────┼────────────┐
              │            │            │
             GPT         Claude       Gemini
```

Bu yapı sizi belirli bir LLM'e bağımlı hale getirmez.

---

# Minimum uygulanabilir versiyon

İlk versiyonda şu 8 parçayı yapmanız yeterli:

```text
1. Constitution
2. User Profile
3. Projects
4. Sessions
5. Memory Notes
6. Sources
7. Context Compiler
8. Memory Manager
```

İlk etapta graph database, karmaşık multi-agent memory veya onlarca memory tipi yapmanıza gerek yok.

Örneğin:

```text
SQLite/Postgres

Memory
Session
Project
Source
Event
Relation
```

ile oldukça ileri gidebilirsiniz.

---

## En önemli prensip

Sisteminizi şu şekilde düşünmeyin:

```text
LLM
 └─ memory
```

Şöyle düşünün:

```text
               Your Personal Knowledge System
                         │
             ┌───────────┼───────────┐
             │           │           │
           Memory      Rules       Projects
             │           │           │
             └───────────┼───────────┘
                         │
                  Context Compiler
                         │
        ┌────────────────┼─────────────────┐
        ▼                ▼                 ▼
       LLM A            LLM B             LLM C
```

**LLM değiştirilebilir bir execution engine; sizin context/memory sisteminiz ise kalıcı işletim sistemi olmalı.**
