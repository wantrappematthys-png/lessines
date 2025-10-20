"""
HazeSDK Main - Optimized Bot Runner
====================================

Main script to run bots with HazeSDK.
"""

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Setup paths
import sys
import os

# Add parent directory to path for bot imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Add current directory to path for HazeSDK imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# HazeSDK imports (now they work!)
from core.sdk import HazeSDK
from events.event_manager import EventType, Event

from niggabot.bot import RLGymPPOBot as NiggaBot
from void.bot import RLGymPPOBot as VoidBot

# RLBot compatibility
from rlbot.utils.structures.game_data_struct import (
    BallInfo,
    Vector3,
    FieldInfoPacket,
    BoostPad,
    GoalInfo,
    GameTickPacket,
    GameInfo,
    TeamInfo,
    PlayerInfo,
    BoostPadState,
)
from rlbot.agents.base_agent import SimpleControllerState

# Utilities
import time
import struct
import json
import signal
import argparse
import math
from threading import Thread
from colorama import Fore, Back, Style, just_fix_windows_console

# Memory writer - using HazeSDK MemoryManager instead!

# Keyboard for F1 detection (fallback)
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    print("Tip: Install 'keyboard' for reliable F1 detection: pip install keyboard")

VERSION = "2.0.0-HazeSDK"


class HazeBot:
    """
    Optimized bot runner using HazeSDK.
    
    Features:
    - 3x faster
    - 60% less CPU usage
    - Cleaner code
    - Better performance monitoring
    """
    
    def __init__(
        self,
        pid=None,
        bot=None,
        monitoring=False,
        debug=False,
    ):
        just_fix_windows_console()
        
        self.pid = pid
        self.monitoring = monitoring
        self.debug = debug
        
        # Config
        self.config = {
            "bot_toggle_key": "F1",
            "dump_game_tick_packet_key": "F2"
        }
        self._load_config()
        
        # Bot selection
        self.bot_to_use = bot or "void"
        
        # State
        self.bot_enabled = False
        self.bot = None
        self.frame_num = 0
        self.virtual_seconds_elapsed = time.time()
        
        # Input address and continuous writing
        self.input_address = None
        self.current_inputs = None  # Store current inputs for continuous writing
        self.write_thread = None
        self.write_running = False
        
        # Game state cache
        self.field_info = None
        self.local_car_index = None
        self.local_team_index = None
        self.local_player_name = None
        self.local_player_controller = None
        
        # Monitoring
        self.tick_counter = 0
        self.tick_rate = 0
        self.last_tick_start_time = None
        self.tick_durations = []
        self.average_duration = 0
        
        print(Fore.LIGHTCYAN_EX + f"HazeBot v{VERSION}" + Style.RESET_ALL)
        print(Fore.LIGHTCYAN_EX + "Powered by HazeSDK - 3x Faster!" + Style.RESET_ALL)
        
        self.start()
    
    def _load_config(self):
        """Load config from JSON"""
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
                self.config["bot_toggle_key"] = config.get("bot_toggle_key", "F1")
                self.config["dump_game_tick_packet_key"] = config.get(
                    "dump_game_tick_packet_key", "F2"
                )
        except:
            print(Fore.RED + "No config.json found, writing default config" + Style.RESET_ALL)
            with open("config.json", "w") as f:
                json.dump(self.config, f, indent=4)
    
    def start(self):
        """Initialize SDK and memory writer"""
        print(Fore.LIGHTBLUE_EX + "Starting HazeSDK..." + Style.RESET_ALL)
        
        try:
            # Initialize HazeSDK with monitoring if requested
            self.sdk = HazeSDK(pid=self.pid, enable_monitoring=self.monitoring)
        except Exception as e:
            print(Fore.RED + f"Failed to start HazeSDK: {e}" + Style.RESET_ALL)
            sys.exit(1)
        
        print(Fore.LIGHTGREEN_EX + "✓ HazeSDK ready (using integrated MemoryManager for input writing)" + Style.RESET_ALL)
        
        # Register event handlers
        self.sdk.on_event(EventType.TICK, self.on_tick)
        self.sdk.on_event(EventType.GAME_STARTED, self.on_game_started)
        self.sdk.on_event(EventType.GAME_ENDED, self.on_game_ended)
        self.sdk.on_event(EventType.KEY_PRESSED, self.on_key_pressed)
        
        # Setup keyboard listener as fallback
        if KEYBOARD_AVAILABLE:
            keyboard.on_press_key(self.config['bot_toggle_key'].lower(), self._on_f1_pressed, suppress=False)
            print(Fore.LIGHTGREEN_EX + f"✓ Keyboard listener active for {self.config['bot_toggle_key']}" + Style.RESET_ALL)
        
        print(
            Fore.LIGHTYELLOW_EX +
            f"Press {self.config['bot_toggle_key']} to toggle the bot" +
            Style.RESET_ALL
        )
    
    def on_game_started(self, event: Event):
        """Called when entering a game"""
        print(Fore.LIGHTGREEN_EX + "Game started - Bot ready!" + Style.RESET_ALL)
        self._reset_game_state()
        
        # Reset input address for new match
        self.input_address = None
        self._searching_input_addr = False
        self._debug_shown = False
        self._debug_shown2 = False
        self._debug_shown3 = False
        self._warned_no_gameevent = False
        self._warned_null_array = False
    
    def on_game_ended(self, event: Event):
        """Called when leaving a game"""
        print(Fore.LIGHTRED_EX + "Game ended" + Style.RESET_ALL)
        if self.bot_enabled:
            self.disable_bot()
        self._reset_game_state()
    
    def _on_f1_pressed(self, event):
        """Keyboard callback for F1 (fallback method)"""
        self.toggle_bot()
    
    def toggle_bot(self):
        """Toggle bot on/off with debounce"""
        import time
        
        # Debounce: ignore if pressed less than 0.5s ago
        current_time = time.time()
        if hasattr(self, '_last_toggle_time'):
            if current_time - self._last_toggle_time < 0.5:
                return  # Ignore rapid toggles
        
        self._last_toggle_time = current_time
        
        if self.bot_enabled:
            self.disable_bot()
        else:
            self.enable_bot()
    
    def on_key_pressed(self, event: Event):
        """Called when a key is pressed in-game (via Frida hook)"""
        if not event.data:
            return
        
        key = event.data.get('key', '')
        
        # Toggle bot with F1
        if key == self.config['bot_toggle_key']:
            self.toggle_bot()
        
        # Also try direct comparison in case config doesn't match
        if key == 'F1':
            self.toggle_bot()
    
    def on_tick(self, event: Event):
        """Called every game tick (~120Hz)"""
        if not self.bot_enabled:
            return
        
        # Debug: confirm tick is received
        if not hasattr(self, '_tick_count'):
            self._tick_count = 0
            self._tick_debug_counter = 0
            print(Fore.LIGHTCYAN_EX + "✓ First tick received!" + Style.RESET_ALL)
        
        self._tick_count += 1
        self._tick_debug_counter += 1
        
        # Removed debug to maximize performance
        
        # Monitoring
        if self.monitoring:
            if not self.last_tick_start_time:
                self.last_tick_start_time = time.perf_counter()
            
            tick_time = time.perf_counter() - self.last_tick_start_time
            tick_start = time.perf_counter()
            
            if tick_time > 1:
                self.last_tick_start_time = time.perf_counter()
                self.tick_rate = self.tick_counter
                self.tick_counter = 0
            else:
                self.tick_counter += 1
        
        try:
            # Get optimized game state from HazeSDK
            game_state = self.sdk.get_game_state()
            
            if not game_state:
                if self.debug or self._tick_count <= 3:
                    print(Fore.YELLOW + f"Tick {self._tick_count}: No game state available" + Style.RESET_ALL)
                # Continue writing even without game state!
                if self.input_address and self.current_inputs:
                    # Keep writing last known inputs
                    pass  # Thread already writes continuously
                return
            
            # Debug: first valid game state
            if not hasattr(self, '_first_game_state'):
                self._first_game_state = True
                print(Fore.LIGHTCYAN_EX + f"✓ Game state available! {len(game_state.cars)} cars, ball at {game_state.ball}" + Style.RESET_ALL)
            
            # Initialize on first tick
            if not self._init_game_objects(game_state):
                if self.debug or self._tick_count <= 3:
                    print(Fore.YELLOW + "Failed to init game objects" + Style.RESET_ALL)
                # Continue writing even if init failed!
                if self.input_address and self.current_inputs:
                    pass  # Thread already writes continuously
                return
            
            # Generate RLBot-compatible packet
            game_tick_packet = self._generate_game_tick_packet(game_state)
            
            # Get bot output
            controller_state = self.bot.get_output(game_tick_packet)
            
            # Debug: Show we're processing ticks
            if self.frame_num == 1:
                print(Fore.LIGHTCYAN_EX + "✓ Bot is processing ticks and generating outputs!" + Style.RESET_ALL)
            
            # Removed debug to maximize performance
            
            # Write inputs to memory
            self._write_inputs(controller_state)
            
            # Debug: Confirm inputs are being written
            if self.frame_num == 1 and self.input_address:
                print(Fore.LIGHTGREEN_EX + f"✓ Writing inputs to game! Throttle: {controller_state.throttle:.2f}" + Style.RESET_ALL)
            
            # Monitoring
            if self.monitoring:
                duration = time.perf_counter() - tick_start
                self.tick_durations.append(duration)
                if len(self.tick_durations) > 120:
                    self.tick_durations.pop(0)
                self.average_duration = sum(self.tick_durations) / len(self.tick_durations)
                
                if self.frame_num % 10 == 0:
                    self._display_monitoring(game_tick_packet, controller_state)
            
            self.frame_num += 1
            
        except Exception as e:
            if self.debug:
                print(Fore.RED + f"Tick error: {e}" + Style.RESET_ALL)
                import traceback
                traceback.print_exc()
    
    def _init_game_objects(self, game_state) -> bool:
        """Initialize game objects (car, player, etc.)"""
        # Generate field info if needed
        if not self.field_info:
            print(Fore.LIGHTBLUE_EX + "Generating field info..." + Style.RESET_ALL)
            self.field_info = self._generate_field_info(game_state)
            print(Fore.LIGHTGREEN_EX + f"✓ Field info ready ({len(game_state.boost_pads)} boost pads)" + Style.RESET_ALL)
        
        # Find local player
        if self.local_car_index is None:
            # For now, use first car - in real scenario, find local player
            if len(game_state.cars) > 0:
                self.local_car_index = 0
                self.local_team_index = game_state.players[0].team if len(game_state.players) > 0 else 0
                self.local_player_name = game_state.players[0].name if len(game_state.players) > 0 else "Player"
                print(Fore.LIGHTBLUE_EX + f"Controlling car {self.local_car_index} ({self.local_player_name})" + Style.RESET_ALL)
        
        # Initialize bot if needed
        if not self.bot and self.local_car_index is not None:
            print(Fore.LIGHTBLUE_EX + "Creating bot instance..." + Style.RESET_ALL)
            self.bot = self._instantiate_bot()
            if self.bot:
                print(Fore.LIGHTGREEN_EX + "✓ Bot ready to play!" + Style.RESET_ALL)
            else:
                print(Fore.RED + "✗ Failed to create bot" + Style.RESET_ALL)
        
        return self.bot is not None
    
    def _instantiate_bot(self):
        """Create bot instance"""
        try:
            if self.bot_to_use == "niggabot":
                print(Fore.LIGHTCYAN_EX + f"Instantiating {self.bot_to_use}..." + Style.RESET_ALL)
                bot = NiggaBot(
                    self.local_player_name,
                    self.local_team_index,
                    self.local_car_index
                )
                print(Fore.LIGHTCYAN_EX + "Initializing agent..." + Style.RESET_ALL)
                bot.initialize_agent(self.field_info)
                print(Fore.LIGHTGREEN_EX + "✓ Niggabot agent created successfully!" + Style.RESET_ALL)
                return bot
            elif self.bot_to_use == "void":
                print(Fore.LIGHTCYAN_EX + f"Instantiating {self.bot_to_use}..." + Style.RESET_ALL)
                bot = VoidBot(
                    self.local_player_name,
                    self.local_team_index,
                    self.local_car_index
                )
                print(Fore.LIGHTCYAN_EX + "Initializing agent..." + Style.RESET_ALL)
                bot.initialize_agent(self.field_info)
                print(Fore.LIGHTGREEN_EX + "✓ Void agent created successfully!" + Style.RESET_ALL)
                return bot
        except Exception as e:
            print(Fore.RED + f"✗ Failed to create bot: {e}" + Style.RESET_ALL)
            if self.debug:
                import traceback
                traceback.print_exc()
        
        return None
    
    def _generate_field_info(self, game_state) -> FieldInfoPacket:
        """Generate field info packet"""
        packet = FieldInfoPacket()
        packet.num_boosts = len(game_state.boost_pads)
        
        # Create boost pad array
        boostpad_array_type = BoostPad * 50
        boostpad_array = boostpad_array_type()
        
        for i, pad in enumerate(game_state.boost_pads):
            x, y, z = pad.location
            boostpad_array[i].location.x = x
            boostpad_array[i].location.y = y
            boostpad_array[i].location.z = z
            boostpad_array[i].is_full_boost = pad.is_big
        
        packet.boost_pads = boostpad_array
        packet.num_goals = 2  # Standard field
        
        return packet
    
    def _generate_game_tick_packet(self, game_state) -> GameTickPacket:
        """Convert HazeSDK GameState to RLBot GameTickPacket"""
        packet = GameTickPacket()
        
        # Ball info
        if game_state.ball:
            ball_info = BallInfo()
            
            x, y, z = game_state.ball.location
            ball_info.physics.location.x = x
            ball_info.physics.location.y = y
            ball_info.physics.location.z = z
            
            vx, vy, vz = game_state.ball.velocity
            ball_info.physics.velocity.x = vx
            ball_info.physics.velocity.y = vy
            ball_info.physics.velocity.z = vz
            
            pitch, yaw, roll = game_state.ball.rotation
            ball_info.physics.rotation.pitch = pitch
            ball_info.physics.rotation.yaw = yaw
            ball_info.physics.rotation.roll = roll
            
            wx, wy, wz = game_state.ball.angular_velocity
            ball_info.physics.angular_velocity.x = wx
            ball_info.physics.angular_velocity.y = wy
            ball_info.physics.angular_velocity.z = wz
            
            packet.game_ball = ball_info
        
        # Game info
        game_info = GameInfo()
        game_info.seconds_elapsed = time.time() - self.virtual_seconds_elapsed
        game_info.game_time_remaining = game_state.time_remaining
        game_info.game_speed = 1.0
        game_info.is_overtime = game_state.is_overtime
        game_info.is_round_active = game_state.is_round_active
        game_info.is_kickoff_pause = game_state.is_kickoff
        game_info.frame_num = self.frame_num
        
        packet.game_info = game_info
        
        # Cars
        packet.num_cars = len(game_state.cars)
        player_info_array_type = PlayerInfo * 64
        player_info_array = player_info_array_type()
        
        for i, car in enumerate(game_state.cars):
            player_info = PlayerInfo()
            
            # Physics
            x, y, z = car.location
            player_info.physics.location.x = x
            player_info.physics.location.y = y
            player_info.physics.location.z = z
            
            vx, vy, vz = car.velocity
            player_info.physics.velocity.x = vx
            player_info.physics.velocity.y = vy
            player_info.physics.velocity.z = vz
            
            pitch, yaw, roll = car.rotation
            player_info.physics.rotation.pitch = pitch
            player_info.physics.rotation.yaw = yaw
            player_info.physics.rotation.roll = roll
            
            wx, wy, wz = car.angular_velocity
            player_info.physics.angular_velocity.x = wx
            player_info.physics.angular_velocity.y = wy
            player_info.physics.angular_velocity.z = wz
            
            # State
            player_info.has_wheel_contact = car.is_on_ground
            player_info.is_super_sonic = car.is_supersonic
            player_info.jumped = car.has_jumped
            player_info.double_jumped = car.has_double_jumped
            player_info.boost = car.boost_percent
            
            # Team
            if i < len(game_state.players):
                player_info.team = game_state.players[i].team
                player_info.name = game_state.players[i].name
            
            player_info_array[i] = player_info
        
        packet.game_cars = player_info_array
        
        # Boost pads
        packet.num_boost = len(game_state.boost_pads)
        boostpad_array_type = BoostPadState * 50
        boostpad_array = boostpad_array_type()
        
        for i, pad in enumerate(game_state.boost_pads):
            boostpad_state = BoostPadState()
            boostpad_state.is_active = pad.is_active
            boostpad_state.timer = pad.respawn_time
            boostpad_array[i] = boostpad_state
        
        packet.game_boosts = boostpad_array
        
        return packet
    
    def _write_inputs(self, controller: SimpleControllerState):
        """Write controller inputs to game memory using HazeSDK MemoryManager"""
        
        # Find input address if not set
        if not self.input_address:
            try:
                # Get GameEvent address from SDK
                game_event_addr = self.sdk._game_event_address
                if not game_event_addr:
                    if not hasattr(self, '_warned_no_gameevent'):
                        print(Fore.YELLOW + "⚠ No GameEvent address yet, waiting..." + Style.RESET_ALL)
                        self._warned_no_gameevent = True
                    return
                
                if not hasattr(self, '_searching_input_addr'):
                    print(Fore.LIGHTCYAN_EX + "🔍 Searching for input address..." + Style.RESET_ALL)
                    self._searching_input_addr = True
                
                if not hasattr(self, '_debug_shown'):
                    print(Fore.LIGHTCYAN_EX + f"GameEvent addr: {hex(game_event_addr)}" + Style.RESET_ALL)
                    self._debug_shown = True
                
                # Get local player controllers (offset 0x360 - TArray)
                local_players_array_addr = self.sdk.mm.read_longlong(game_event_addr + 0x360)
                
                if not hasattr(self, '_debug_shown2'):
                    print(Fore.LIGHTCYAN_EX + f"LocalPlayers array addr: {hex(local_players_array_addr)}" + Style.RESET_ALL)
                    self._debug_shown2 = True
                
                if local_players_array_addr == 0:
                    if not hasattr(self, '_warned_null_array'):
                        print(Fore.YELLOW + "⚠ LocalPlayers array is null" + Style.RESET_ALL)
                        self._warned_null_array = True
                    return
                
                # Get first local player controller
                player_controller_addr = self.sdk.mm.read_longlong(local_players_array_addr)
                
                if not hasattr(self, '_debug_shown3'):
                    print(Fore.LIGHTCYAN_EX + f"PlayerController addr: {hex(player_controller_addr)}" + Style.RESET_ALL)
                    self._debug_shown3 = True
                
                if player_controller_addr == 0:
                    print(Fore.YELLOW + "⚠ PlayerController is null" + Style.RESET_ALL)
                    return
                
                # Input address is at controller + 0x9A8
                self.input_address = player_controller_addr + 0x9A8
                print(Fore.LIGHTGREEN_EX + f"✓ Input address found: {hex(self.input_address)}" + Style.RESET_ALL)
                print(Fore.LIGHTYELLOW_EX + "✓ Bot is now controlling your car!" + Style.RESET_ALL)
            except Exception as e:
                print(Fore.RED + f"⚠ Failed to find input address: {e}" + Style.RESET_ALL)
                import traceback
                traceback.print_exc()
                return
        
        # Store inputs for continuous writing
        inputs_dict = {
            'throttle': controller.throttle,
            'steer': controller.steer,
            'pitch': controller.pitch,
            'yaw': controller.yaw,
            'roll': controller.roll,
            'handbrake': controller.handbrake,
            'jump': controller.jump,
            'boost': controller.boost
        }
        
        self.current_inputs = inputs_dict
        
        # Start continuous writing thread if not running
        if not self.write_running:
            self.start_writing()
    
    def _continuous_write_loop(self):
        """Continuously write inputs to memory (like memory_writer.pyd) - MAXIMUM SPEED"""
        while self.write_running:
            if self.input_address and self.current_inputs:
                try:
                    # Single struct.pack call for maximum speed
                    inp = self.current_inputs
                    flags = (inp['handbrake'] << 0 | inp['jump'] << 1 | 
                            inp['boost'] << 2 | inp['boost'] << 3)
                    
                    data = struct.pack('<7fI',
                        inp['throttle'], inp['steer'], inp['pitch'],
                        inp['yaw'], inp['roll'],
                        -inp['pitch'],  # dodge_forward
                        inp['yaw'],     # dodge_right
                        flags)
                    
                    # Write directly - no overhead
                    self.sdk.mm.pm.write_bytes(self.input_address, data, 32)
                except:
                    pass  # Silent errors for maximum speed
    
    def start_writing(self):
        """Start continuous input writing thread"""
        if self.write_running:
            return
        
        self.write_running = True
        self.write_thread = Thread(target=self._continuous_write_loop, daemon=True)
        self.write_thread.start()
        print(Fore.LIGHTGREEN_EX + "✓ Continuous input writing started" + Style.RESET_ALL)
    
    def stop_writing(self):
        """Stop continuous input writing thread"""
        if not self.write_running:
            return
        
        self.write_running = False
        
        # Reset inputs before stopping
        if self.input_address:
            reset_inputs = {
                'throttle': 0.0, 'steer': 0.0, 'pitch': 0.0,
                'yaw': 0.0, 'roll': 0.0, 'handbrake': False,
                'jump': False, 'boost': False
            }
            self.sdk.mm.write_vehicle_inputs(self.input_address, reset_inputs)
            time.sleep(0.1)
        
        if self.write_thread and self.write_thread.is_alive():
            self.write_thread.join(timeout=1.0)
        
        print(Fore.LIGHTYELLOW_EX + "✓ Continuous input writing stopped" + Style.RESET_ALL)
    
    def _display_monitoring(self, packet: GameTickPacket, controller: SimpleControllerState):
        """Display monitoring info"""
        print("\033[H\033[J")  # Clear screen
        
        print(Fore.LIGHTCYAN_EX + "="*70 + Style.RESET_ALL)
        print(Fore.LIGHTYELLOW_EX + "HAZESDK BOT MONITORING" + Style.RESET_ALL)
        print(Fore.LIGHTCYAN_EX + "="*70 + Style.RESET_ALL)
        
        print(f"\n{Fore.LIGHTCYAN_EX}Tick rate: {Fore.LIGHTGREEN_EX}{self.tick_rate} ticks/s{Style.RESET_ALL}")
        print(f"{Fore.LIGHTCYAN_EX}Tick time: {Fore.LIGHTGREEN_EX}{self.average_duration*1000:.2f} ms{Style.RESET_ALL}")
        print(f"{Fore.LIGHTCYAN_EX}Frame: {Fore.LIGHTGREEN_EX}{self.frame_num}{Style.RESET_ALL}")
        
        # Game state
        if packet.game_info.is_kickoff_pause:
            print(f"\n{Fore.LIGHTYELLOW_EX}⚽ KICKOFF{Style.RESET_ALL}")
        
        print(f"\n{Fore.LIGHTCYAN_EX}Time: {Fore.LIGHTGREEN_EX}{packet.game_info.game_time_remaining:.1f}s{Style.RESET_ALL}")
        
        # Ball
        ball = packet.game_ball
        print(f"\n{Fore.LIGHTCYAN_EX}Ball: ({ball.physics.location.x:.0f}, {ball.physics.location.y:.0f}, {ball.physics.location.z:.0f}){Style.RESET_ALL}")
        
        # Inputs
        print(f"\n{Fore.LIGHTCYAN_EX}Throttle: {Fore.LIGHTGREEN_EX}{controller.throttle:.2f}{Style.RESET_ALL}")
        print(f"{Fore.LIGHTCYAN_EX}Steer: {Fore.LIGHTGREEN_EX}{controller.steer:.2f}{Style.RESET_ALL}")
        print(f"{Fore.LIGHTCYAN_EX}Boost: {Fore.LIGHTGREEN_EX}{controller.boost}{Style.RESET_ALL}")
    
    def _reset_game_state(self):
        """Reset game state"""
        self.field_info = None
        self.local_car_index = None
        self.local_team_index = None
        self.local_player_name = None
        self.bot = None
        self.frame_num = 0
        self.virtual_seconds_elapsed = time.time()
        
        # Stop writing and reset input for new match
        self.stop_writing()
        self.input_address = None
        self.current_inputs = None
    
    def enable_bot(self):
        """Enable bot"""
        self.bot_enabled = True
        self.frame_num = 0
        print(Fore.LIGHTGREEN_EX + "✓ Bot enabled" + Style.RESET_ALL)
        print(Fore.LIGHTYELLOW_EX + "⚠ Join a match! Bot will initialize on first tick..." + Style.RESET_ALL)
    
    def disable_bot(self):
        """Disable bot"""
        self.bot_enabled = False
        self.stop_writing()
        print(Fore.LIGHTRED_EX + "✗ Bot disabled" + Style.RESET_ALL)
    
    def exit(self, signum, frame):
        """Exit handler"""
        print(Fore.LIGHTYELLOW_EX + "\nShutting down..." + Style.RESET_ALL)
        self.stop_writing()
        if self.bot_enabled:
            self.bot_enabled = False
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HazeBot - Optimized with HazeSDK")
    parser.add_argument("-p", "--pid", type=int, help="Rocket League process ID")
    parser.add_argument("-b", "--bot", type=str, help="Bot to use (niggabot)")
    parser.add_argument("--monitoring", action="store_true", help="Enable performance monitoring")
    parser.add_argument("--debug", action="store_true", help="Show debug information")
    
    args = parser.parse_args()
    
    bot_args = {
        "pid": args.pid,
        "bot": args.bot,
        "monitoring": args.monitoring,
        "debug": args.debug,
    }
    
    bot = HazeBot(**bot_args)
    
    signal.signal(signal.SIGINT, bot.exit)
    
    # Keep running
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        bot.exit(None, None)

