## Context

The source setup blocks install the nlp extra, download Stanza resources, and
start the server with the linguistic model directory option. The Docker
quick-start currently builds the image, creates the named volume, downloads a
voice, and starts the server, but leaves Stanza preparation and the linguistic
model directory option to a later detailed section. The Dockerfile currently
keeps that extra out of the default image and documents a separate NLP profile.
The shared analyzer currently hard-codes
tokenize,mwt,pos,lemma,depparse, although the Vietnamese resource downloaded
by Stanza does not contain an mwt model.

The existing Docker storage contract remains valid: voices, coordination state,
and linguistic resources belong in one Docker-managed named volume mounted at
/data. The source environment may use its existing local or temporary paths;
parity means the runtime behavior and resource selection are shared, not that
host paths are reused by Docker.

## Goals / Non-Goals

**Goals:**

- Make the standard Docker image provide the same Stanza capability as the
  supported source installation.
- Avoid CUDA/NVIDIA packages in the CPU Docker runtime.
- Keep large Stanza model weights out of the image and persist them in
  /data/stanza.
- Use one language-to-processor mapping for model preparation and pipeline
  loading on both host and Docker.
- Make the copyable Docker quick-start sequence prepare Stanza resources before
  starting the server, so its first analysis request exercises the standard
  NLP-enabled flow.
- Download only the processor models required by the supported analysis output.
- Keep missing-resource fallback, port 5000, named-volume persistence, and
  existing HTTP schemas stable.

**Non-Goals:**

- Do not change the /analyze request or response schema.
- Do not bake voice models, Stanza model weights, GGUF files, or llama.cpp into
  the Piper image.
- Do not require host bind mounts for Docker runtime data.
- Do not add automatic network downloads during synthesis or analysis requests.
- Do not introduce a separate Docker-only linguistic implementation.
- Do not change acoustic models or basic Vietnamese, Japanese, or Chinese
  synthesis behavior.

## Decisions

### Use one standard NLP-enabled Docker runtime

The final Docker image will install the runtime extras required by the current
source setup, including nlp. The image build will install a CPU-only PyTorch
distribution or equivalent platform constraint and will fail validation if it
resolves the CUDA/NVIDIA runtime tree.

Keeping NLP in a separate optional image is rejected because it leaves the
documented Docker runtime behavior different from the source behavior. Pulling
the default PyTorch distribution is rejected because it caused a large
CUDA-enabled dependency tree on the target ARM64 build. The exact CPU wheel
selection must be validated on the supported Python and Docker platforms.

### Share the processor mapping between preparation and analysis

Introduce a small shared resource definition in the Piper Python package. It
will define the supported pilot languages and the processors required for each
language. The resource preparation command and StanzaLinguisticAnalyzer will
both consume this definition.

The mapping will include mwt only for languages whose Stanza resources expose
and require that processor. Vietnamese and any other language without a usable
mwt model will use the remaining processors needed by the serialized output.
The implementation will verify the mapping against installed Stanza resource
metadata rather than assuming every language has the same pipeline.

This is preferred over duplicating processor strings in shell snippets and
analysis code because duplicated lists already caused the Docker/source
resource flow and runtime pipeline to diverge.

### Provide one explicit resource-preparation interface

The package will expose a Python resource-preparation command that accepts a
model directory and an optional language selection. Host documentation will
invoke it directly. The Docker entrypoint will delegate to the same command
with /data/stanza as its model directory.

Resources will be downloaded explicitly before server startup and will never be
downloaded as a side effect of /analyze, /synthesize, or ordinary voice
download requests. The default language selection may cover the five supported
pilot languages, while a language selection can avoid downloading unused model
sets.

The Docker quick-start will call this interface as a one-time volume setup step
and will start the server with `/data/stanza` explicitly configured. The
detailed Docker section may explain the same commands further, but it will not
be the only place where the complete NLP flow is documented.

### Keep model weights in the named volume

The image will contain the Stanza Python runtime but not language model weights.
The documented Docker flow will create or reuse piper-data, prepare models at
/data/stanza, and start the server with the linguistic model directory option.
Removing and recreating the container will preserve the models; deleting the
volume remains an explicit destructive operation.

### Preserve fallback and API compatibility

If Stanza is unavailable or a requested language resource is incomplete, the
analyzer will return the existing local fallback status rather than preventing
basic speech synthesis. When the shared processor set and resources are
complete, /analyze will report Stanza as its source for the supported language.
Existing serialized fields remain stable; fields that depend on an unavailable
processor remain absent according to current serialization rules.

## Risks / Trade-offs

- **CPU wheel availability** -> Validate the selected CPU-only PyTorch
  distribution on Python 3.12 and the target Docker architecture; fail the
  image check if CUDA packages appear.
- **NLP image remains larger than the base image** -> Keep model weights in the
  named volume, download only selected languages/processors, and measure image
  and volume contents separately.
- **Stanza resource metadata can change** -> Validate processor mappings against
  downloaded resource metadata and test all supported pilot languages.
- **Processor differences can change analysis detail** -> Preserve the existing
  JSON contract, test token/lemma/POS/dependency fields where available, and
  retain local fallback for incomplete resources.
- **Resource download requires network access during preparation** -> Make the
  preparation step explicit and repeatable; server and synthesis remain usable
  from prepared volume data without a network dependency.

## Migration Plan

1. Build the unified image with the CPU-only NLP dependency constraint.
2. Create or reuse the Docker-managed piper-data volume.
3. Run the shared Stanza resource-preparation command for required languages,
   storing models under /data/stanza.
4. Download the required voice into the same named volume.
5. Start the server on 5000:5000 with /data mounted and the linguistic model
   directory set to /data/stanza.
6. Verify /analyze, /synthesize, UI, catalog, download persistence, and
   fallback behavior.
7. Roll back by using the previous image and its existing named volume; do not
   delete the volume during rollback.

## Open Questions

None.
