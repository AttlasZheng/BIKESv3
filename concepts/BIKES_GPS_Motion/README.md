# BIKES GPS Motion

GPS-driven audio playback and motion matching across four BIKES nodes.

Each Raspberry Pi reads its own GPS sensor, detects acceleration, deceleration, left turns, and right turns, and controls a local SuperCollider file player. When another bike detects the same motion within the matching window, it adopts the audio selection announced by the first bike.

## Files

| File | Purpose |
|---|---|
| `concepts/gps_motion/PixelGPS.py` | Reads GPS data, detects motion, exchanges peer OSC messages, and sends playback commands to local SuperCollider. |
| `concepts/gps_motion/GPSListener.scd` | Preloads local WAV files, starts background playback, and crossfades between files on motion commands. |
| `concepts/gps_motion/gps_motion.yml` | Starts JACK, SuperCollider, and the Python process on all four Raspberry Pis. |
| `tests/test_gps_motion.py` | Tests GPS parsing, motion detection, and peer-event matching. |

The names and variables follow the existing BIKES code style, including `soundscape`, `remote_app_dir`, `~host`, `~absolutePrefix`, `~absolute`, and `~rSound`. The Python program runs without a graphical interface. This module communicates directly over OSC using the four Pi IP addresses; P2PSC and Ableton Link are not required.

## Playback and Matching Behavior

1. Each bike starts by looping its local `base/0.wav`.
2. When local GPS data indicates a significant motion, Python announces a `/motionShare` event to the other three bikes.
3. If no recent event of that type exists, the bike randomly selects an audio number for that motion.
4. Receiving bikes cache the announcement. A remote announcement alone does not trigger playback.
5. If a receiving bike detects the same motion while the announcement is still inside the matching window, it uses the earliest event's audio number.
6. After local motion detection, Python waits for the configurable settling period to collect nearly simultaneous announcements, then sends `/motion` to local SuperCollider.
7. SuperCollider fades out the old player, releases it, and fades in the selected file. The new file loops until another motion command switches it.

The default matching window is **8 seconds** and the default settling period is **0.6 seconds**. Left and right turns are separate event types. Earlier timestamps take priority; equal timestamps are ordered by bike ID and then event ID.

For example, if bike 1 detects acceleration and chooses `accelerate/2.wav`, bike 2 will play its own copy of that file if it also detects acceleration within the matching window. A bike without matching local motion continues its current playback.

Matching selects the same audio file. Each bike starts playback after its own motion detection, so this module does not align playback positions or start times. Recent matching events carry forward the earliest available selection; a new random selection is made when no recent event of that type remains.

Stopping or losing GPS reception leaves the current audio playing. It does not automatically restore the background file.

## Project Placement and Audio Files

Copy the package's `concepts/gps_motion/` directory into the BIKESv3 `concepts/` directory. Deploy the code and media to `~/Desktop/BIKES/` on every bike.

All bikes must have the same media directory structure and identical audio content. The default theme is `marine`, with `sample_count=4`:

| Path relative to the BIKES project root | Purpose |
|---|---|
| `media/gps_motion/samples/marine/base/0.wav` | Startup background loop |
| `media/gps_motion/samples/marine/accelerate/0.wav` through `3.wav` | Acceleration samples |
| `media/gps_motion/samples/marine/decelerate/0.wav` through `3.wav` | Deceleration samples |
| `media/gps_motion/samples/marine/turn_left/0.wav` through `3.wav` | Left-turn samples |
| `media/gps_motion/samples/marine/turn_right/0.wav` through `3.wav` | Right-turn samples |

The default configuration requires **17 WAV files**. Mono and stereo files are supported. Audio assets are not included in this package. For an initial test, a short WAV can be copied to the required filenames and replaced with your own sounds later.

To use another theme, create its folder and pass `soundscape=YOUR_THEME`. To change the number of samples per motion, set `sample_count`; the playbook passes that count to both Python and SuperCollider.

Buffers are loaded once at startup. Motion events reuse the loaded buffers, and the outgoing synth is released after its fade-out.

## GPS Input and Detection

The default serial device is `/dev/ttyACM0` at **9600 baud**. For manual Python testing on Windows, use the sensor's COM port, such as `COM3`.

The parser accepts checksum-verified RMC and GGA sentences, including `$GPRMC` and `$GNRMC`:

- RMC ground speed is converted from knots to metres per second.
- Acceleration is estimated from changes in smoothed speed using a sliding regression window.
- Turning is estimated from course-over-ground changes. Shortest signed angle differences handle north crossings such as 359 degrees to 1 degree.
- GPS UTC date and time determine sample intervals, avoiding derivatives based on serial arrival timing.
- RMC status `V`, invalid velocity data, or poor recent GGA quality clears the detection history.
- If recent GGA data is available, it must indicate a valid fix, at least four satellites, and HDOP no greater than four. Valid RMC data can be used when GGA is unavailable.
- More than four seconds without valid fixes clears the history. A disconnected serial device is retried every three seconds.
- Turning is disabled below 1.5 m/s. GPS course-over-ground cannot reliably detect a stationary handlebar turn.

RMC sentences with valid speed are required. GGA-only or VTG-only output cannot drive this detector. RMC speed can still support acceleration detection when its course field is empty.

### Detection Parameters

The following variables can be configured in `gps_motion.yml` or supplied as Ansible extra variables:

| Variable | Default | Meaning |
|---|---:|---|
| `accel_threshold` | 0.6 | Acceleration threshold, m/s² |
| `decel_threshold` | 0.6 | Deceleration magnitude threshold, m/s² |
| `turn_rate` | 10 | Course change rate threshold, degrees/s |
| `turn_angle` | 25 | Net course change threshold within the window, degrees |
| `min_turn_speed` | 1.5 | Minimum speed for turn detection, m/s |
| `window` | 2.5 | Regression window, seconds |
| `min_span` | 1.0 | Minimum time span required for regression, seconds |
| `smoothing` | 0.8 | Speed smoothing time constant, seconds |
| `confirm_samples` | 2 | Consecutive qualifying RMC samples required |
| `cooldown` | 5 | Minimum interval between triggers of the same type, seconds |
| `match_window` | 8 | Peer-event matching window, seconds |
| `settle_time` | 0.6 | Announcement collection period before local playback, seconds |
| `max_hdop` | 4 | Maximum accepted recent GGA HDOP |
| `min_satellites` | 4 | Minimum satellite count when recent GGA is available |

A sustained motion triggers once. Its detection score must fall below 70% of the threshold before it can trigger again, and the cooldown must also have elapsed. If one GPS fix qualifies for multiple motion types, the strongest normalized motion is selected.

These defaults are starting values. Tune them using the actual sensor output. With a 1 Hz GPS and the default filtering and confirmation, detection can take several seconds and may miss brief braking or turning movements. A higher GPS update rate or an additional IMU can improve responsiveness.

## OSC Communication and Clock Synchronization

| Route | Destination | Arguments |
|---|---|---|
| `/motionShare` | Other bikes' Python receivers, UDP 57121 | Event ID, source bike ID, motion type, audio number, creation timestamp |
| `/motion` | Local SuperCollider, `127.0.0.1:57120` | Motion type, audio number, local trigger ID, selected source bike ID, acceleration, turn rate |

Peer announcements are sent three times and deduplicated by event ID. Peer reception only caches candidates; playback requires local GPS detection.

Synchronize all four Pi system clocks using the project's existing **Chrony/NTP configuration** before running. Peer event ordering uses system UTC time. Timestamps are encoded as strings to preserve precision that would be lost with OSC float32 values.

By default, incoming events must be within the matching window and no more than one second ahead of the receiver's clock. UDP packet loss or announcements delayed beyond the settling period can affect first-event selection. The protocol does not guarantee agreement under arbitrary network delays or packet loss.

Allow peer-to-peer traffic on UDP 57121. Local Python-to-SuperCollider commands use UDP 57120. If the bikes' IP addresses differ from the original project, update `bikes_ips` in the playbook or override it with extra variables.

## Four-Bike Deployment

### Prerequisites

Each bike needs:

- The module code and all required WAV files under `~/Desktop/BIKES/`.
- SuperCollider and JACK.
- A Python environment containing `pyserial` and `python-osc`.
- Read and write access to the GPS serial device for its `bikes1` through `bikes4` user.
- Synchronized system clocks and network connectivity to the other bikes.

The playbook starts files already present on each bike; it does not synchronize project files. The existing `sync_folder.yml` uses deletion during mirroring, so make sure the local media tree is complete before using it.

On Linux, serial access usually requires membership in the `dialout` group, followed by a new login. Confirm which device is the GPS sensor, especially when a UWB device is also attached. Stable `/dev/serial/by-id/` paths can also be supplied as GPS device paths.

### Inventory

Use the existing inventory file at `utility/config/bikes.ini`. Per-bike serial and audio device overrides can be added as follows:

```ini
[bikes]
10.10.10.11 ansible_user=bikes1 gps_serial_port=/dev/ttyACM0 bikes_audio_device=hw:2,0
10.10.10.12 ansible_user=bikes2 gps_serial_port=/dev/ttyACM0 bikes_audio_device=hw:2,0
10.10.10.13 ansible_user=bikes3 gps_serial_port=/dev/ttyACM0 bikes_audio_device=hw:2,0
10.10.10.14 ansible_user=bikes4 gps_serial_port=/dev/ttyACM0 bikes_audio_device=hw:2,0
```

The playbook expects exactly four hosts in the `bikes` group, using the users `bikes1`, `bikes2`, `bikes3`, and `bikes4`.

### Start the Module

From the BIKESv3 project root:

```bash
ansible-playbook -i ./utility/config/bikes.ini \
  concepts/gps_motion/gps_motion.yml
```

For a first installation, enable dependency installation. This requires network access and sudo permissions on the bikes:

```bash
ansible-playbook -K -i ./utility/config/bikes.ini \
  concepts/gps_motion/gps_motion.yml -e install_dependencies=true
```

This installs SuperCollider, JACK, and Python tooling, then installs `pyserial` and `python-osc` into the module's `.venv`. By default, dependency installation is disabled. The playbook uses that virtual environment if present, otherwise `/usr/bin/python3`.

For offline operation, install the dependencies in advance. Add `-k` if SSH password authentication is needed, or `-K` if sudo requires a password.

To override the GPS port and a threshold for all bikes:

```bash
ansible-playbook -i ./utility/config/bikes.ini \
  concepts/gps_motion/gps_motion.yml \
  -e 'gps_port=/dev/ttyUSB1 soundscape=marine accel_threshold=0.8'
```

The playbook checks the scripts, media files, dependencies, and serial permissions before stopping the current audio stack. It stops the previous `PixelGPS.py` process and the current user's `sclang`, `scsynth`, and `jackd` processes. It then checks that the peer OSC port is available, starts JACK and SuperCollider, waits for the audio buffers and OSC listener to be ready, and starts Python.

Use this module as the active audio concept on each bike. Startup replaces the existing audio stack. Unrelated Python programs are left running.

## Manual Single-Bike Testing

On the Pi, start JACK with the appropriate audio device, then run:

```bash
cd ~/Desktop/BIKES/concepts/gps_motion
sclang GPSListener.scd marine 4
```

In another terminal:

```bash
.venv/bin/python PixelGPS.py marine --host 1 \
  --gps-port /dev/ttyACM0 --baud-rate 9600 --verbose
```

Use `python3` instead of `.venv/bin/python` if the dependencies are installed in the system environment. Set `--host` to the actual bike ID. Run `PixelGPS.py --help` to see the available command-line options.

Wait for a valid GPS fix. Inspect the verbose speed, acceleration, and turn-rate output before adjusting thresholds and testing all four bikes.

A received peer announcement should log:

```text
Cached ... (no local playback)
```

A matching local motion should produce:

```text
PLAY ... chosen by bike ...
```

## Troubleshooting

The playbook writes logs to each bike's `concepts/gps_motion/` directory:

| Log | What to check |
|---|---|
| `gps_log.txt` | Serial connection, detected motion, peer events, selected audio numbers |
| `sc_log.txt` | Missing WAV files, audio server errors, readiness, current playback |
| `jack_log.txt` | Audio device selection and JACK startup errors |

If startup times out waiting for readiness, inspect `sc_log.txt` first. If UDP 57121 is occupied, stop the other concept using that port or configure another peer port consistently on all bikes.

If no motion is detected, check the serial path, baud rate, access permissions, valid RMC output, recent GGA quality, and thresholds. Missing or invalid GPS data leaves current audio playing and does not generate new motion events.

If matching fails, check peer IP addresses, UDP connectivity, clock synchronization, matching-window settings, and identical media contents across bikes.

## Validation

Run the included tests from the package root:

```bash
python3 -m unittest discover -s tests -v
```

The 26 automated tests cover NMEA checksums, units, midnight rollover, acceleration and deceleration, left and right turns, heading wraparound, low-speed heading noise, duplicate timestamps, GPS gaps, remote-only caching, matching and nonmatching motions, expired events, event ordering, duplicates, and timestamp precision.

Validation completed during development:

- All 26 automated tests passed.
- A simulated GPS serial device and real UDP OSC messages exercised the Python process end to end.
- Four independent Python processes confirmed that the first bike selected an audio number, two bikes adopted it after matching local acceleration, and a fourth bike without local motion did not trigger playback.
- The Ansible playbook passed its syntax check.

SuperCollider audio playback, physical GPS sensitivity, Raspberry Pi audio devices, and the four-bike wireless network still require testing on the actual hardware.
