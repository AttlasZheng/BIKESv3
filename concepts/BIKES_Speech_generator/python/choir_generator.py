import os
import re
import yaml
import argparse
import numpy as np
import soundfile as sf
from kokoro import KPipeline
from scipy.signal import resample_poly

def get_lang_from_voice(voice_name):
    if voice_name.startswith("b"):
        return "b"
    return "a"

def main():
    parser = argparse.ArgumentParser(
        description="BIKES Speech generator: Multi-Pipeline Generation with Spliced Phrase Outputs."
    )
    parser.add_argument(
        "-i", "--input",
        type=str,
        required=True,
        help="Path to the piece text file (e.g., texts/flock_speech.txt)"
    )
    parser.add_argument(
        "-c", "--config",
        type=str,
        required=True,
        help="Path to the explicit YAML configuration file (e.g., texts/flock_choir.yaml)"
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default="flock",
        help="Directory where generated audio files are written."
    )

    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"Error: Config file '{args.config}' not found.")
        return

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    speed = float(cfg.get("speed", 0.92))
    coupling_weight = float(cfg.get("coupling_weight", 0.7))
    reference_voice = str(cfg.get("reference_voice", "bf_emma"))
    choir_voices = cfg.get("choir_voices", [])

    if not os.path.exists(args.input):
        print(f"Error: Input text target '{args.input}' not found.")
        return

    # ---- PARSE PHRASES AND INTERNAL SEGMENTS ----
    with open(args.input, "r", encoding="utf-8") as f:
        raw_blocks = f.read().split("\n\n")

    # List of tuples: (phrase_index, list_of_active_segment_strings)
    phrase_matrix = []

    for p_idx, block in enumerate(raw_blocks, 1):
        cleaned_block = block.strip()
        if not cleaned_block:
            continue

        # Skip entire phrase slot if globally commented out
        if cleaned_block.startswith("#"):
            print(f"  [Skipping Entire Phrase Slot {p_idx}]: Block commented out.")
            continue

        raw_lines = cleaned_block.split("\n")
        active_segments = []

        for s_idx, line in enumerate(raw_lines, 1):
            cleaned_line = line.strip()
            if not cleaned_line:
                continue

            # Skip single line segment if commented out internally
            if cleaned_line.startswith("#"):
                print(f"    [Skipping Line Slot p{p_idx}_s{s_idx}]: Line commented out.")
                continue

            active_segments.append(cleaned_line)

        if active_segments:
            phrase_matrix.append((p_idx, active_segments))

    if not phrase_matrix:
        print("No active text segments discovered to render.")
        return

    os.makedirs(args.output_dir, exist_ok=True)
    file_base_name = os.path.splitext(os.path.basename(args.input))[0]

    # Initialize parallel phonetic pipelines
    pipelines = {
        "a": KPipeline(lang_code="a"),
        "b": KPipeline(lang_code="b")
    }

    ref_lang = get_lang_from_voice(reference_voice)
    ref_emb = pipelines[ref_lang].load_voice(reference_voice)

    # ---- CHORAL RENDER MATRIX ----
    for phrase_idx, segments in phrase_matrix:
        print(f"\nProcessing Phrase {phrase_idx} ({len(segments)} segments)...")

        for voice_idx, target_voice in enumerate(choir_voices, 1):
            # Verify voice actor is active
            if str(target_voice).startswith("#") or not target_voice:
                print(f"  -> Voice Track {voice_idx} is muted in configuration. Skipping.")
                continue

            target_lang = get_lang_from_voice(target_voice)
            active_pipeline = pipelines[target_lang]

            try:
                target_emb = active_pipeline.load_voice(target_voice)
            except Exception as e:
                print(f"  -> Error loading voice profile {target_voice}: {e}")
                continue

            # Blend embeddings
            choir_member_emb = ((1.0 - coupling_weight) * ref_emb) + (coupling_weight * target_emb)

            phrase_audio_chunks = []

            # Synthesize each line segment sequentially for the current voice
            for seg_text in segments:
                generator = active_pipeline(
                    seg_text,
                    voice=choir_member_emb,
                    speed=speed,
                    split_pattern=None
                )

                for _, _, audio in generator:
                    phrase_audio_chunks.append(audio)

            # Splicing: Concatenate all segment audio streams for this phrase
            if phrase_audio_chunks:
                final_phrase_audio = np.concatenate(phrase_audio_chunks)

               # Naming layout: sentence_N_voice_M.wav
                filename = f"sentence_{phrase_idx}_voice_{voice_idx}.wav"
                output_path = os.path.join(args.output_dir, filename)

                audio_48k = resample_poly(final_phrase_audio, up=2, down=1)

                sf.write(output_path, audio_48k, 48000, subtype="PCM_16")
                print(f"  -> Generated: {filename}")

    print(f"\nStems updated successfully inside: /{args.output_dir}")

if __name__ == "__main__":
    main()