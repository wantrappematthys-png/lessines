"""
HazeSDK Main
============

Main SDK class that orchestrates everything.
"""

import frida
from typing import Optional, Callable
import sys
import os
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from core.memory_manager import MemoryManager
from core.offset_scanner import OffsetScanner
from game_objects.game_state import GameState
from events.event_manager import EventManager, EventType, Event
from utils.constants import *
from utils.performance import PerformanceMonitor


# Frida script for function hooking
FRIDA_SCRIPT = """
var processEventAddress = null;
var hooks = {};
var hookedFunctions = new Map();
var processEventHooked = false;

rpc.exports = {
    setProcessEventAddress: function(addr) {
        if (processEventHooked) {
            return;
        }
        
        processEventAddress = ptr(addr);
        console.log('[Frida] Hooking ProcessEvent at ' + addr);
        
        // Hook ProcessEvent to intercept all UFunction calls
        Interceptor.attach(processEventAddress, {
            onEnter: function(args) {
                // args[0] = this (UObject*)
                // args[1] = UFunction*
                var uFunction = args[1];
                var funcAddr = uFunction.toString();
                
                // Check if this function is hooked
                if (hookedFunctions.has(funcAddr)) {
                    var funcInfo = hookedFunctions.get(funcAddr);
                    var data = {
                        type: 'function_called',
                        name: funcInfo.name,
                        caller: args[0].toString(),
                        function: funcAddr,
                        timestamp: Date.now(),
                        args: {}
                    };
                    
                    // Extract args if needed
                    if (funcInfo.argsMap && Array.isArray(funcInfo.argsMap)) {
                        for (var i = 0; i < funcInfo.argsMap.length; i++) {
                            var argInfo = funcInfo.argsMap[i];
                            var argIndex = argInfo.index || 2;  // Default to index 2 (params)
                            var argType = argInfo.type || 'pointer';
                            var argName = argInfo.name || ('arg' + argIndex);
                            
                            try {
                                if (argType === 'bytes' && argInfo.size) {
                                    var bytes = args[argIndex].readByteArray(argInfo.size);
                                    var hexStr = '';
                                    var arr = new Uint8Array(bytes);
                                    for (var j = 0; j < arr.length; j++) {
                                        var hex = arr[j].toString(16);
                                        hexStr += (hex.length === 1 ? '0' : '') + hex;
                                    }
                                    data.args[argName] = hexStr;
                                } else if (argType === 'float') {
                                    data.args[argName] = args[argIndex].readFloat();
                                } else if (argType === 'int') {
                                    data.args[argName] = args[argIndex].toInt32();
                                } else {
                                    data.args[argName] = args[argIndex].toString();
                                }
                            } catch (e) {
                                // Ignore errors reading args
                            }
                        }
                    }
                    
                    send(data);
                }
            }
        });
        
        processEventHooked = true;
        console.log('[Frida] ProcessEvent hooked successfully');
    },
    
    hookFunction: function(funcAddr, funcName, argsMap) {
        console.log('[Frida] Registering hook for ' + funcName + ' at ' + funcAddr);
        
        // Store function info for ProcessEvent to check
        hookedFunctions.set(funcAddr, {
            name: funcName,
            argsMap: argsMap || []
        });
        
        hooks[funcName] = true;
        return true;
    }
};
"""


class HazeSDK:
    """
    High-performance Rocket League SDK.
    
    Features:
    - Automatic offset detection
    - Optimized memory access
    - Event-driven architecture
    - Performance monitoring
    
    Example:
        sdk = HazeSDK()
        
        @sdk.on_tick
        def on_game_tick(event):
            game_state = sdk.get_game_state()
            # ... use game state ...
    """
    
    def __init__(self, pid: Optional[int] = None, enable_monitoring: bool = False):
        """
        Initialize SDK.
        
        Args:
            pid: Process ID (optional, will find RocketLeague.exe)
            enable_monitoring: Enable performance monitoring
        """
        print("[HazeSDK] Initializing...")
        
        # Core components
        self.mm = MemoryManager(PROCESS_NAME, pid)
        self.event_manager = EventManager()
        self.perf_monitor = PerformanceMonitor()
        
        if not enable_monitoring:
            self.perf_monitor.disable()
        
        # Find offsets
        self._find_offsets()
        
        # Game state
        self._game_event_address: Optional[int] = None
        self._game_state: Optional[GameState] = None
        
        # Frida for hooking
        self._frida_session: Optional[frida.core.Session] = None
        self._frida_script = None
        
        # GNames and GObjects
        self._gnames = {}
        self._static_functions = {}
        
        # Initialize
        self._init_frida()
        self._load_gnames()
        self._find_functions()
        self._setup_hooks()
        
        print("[HazeSDK] ✓ Initialization complete")
    
    def _find_offsets(self):
        """Find GNames and GObjects offsets"""
        scanner = OffsetScanner(self.mm)
        gnames_offset, gobjects_offset = scanner.find_offsets()
        
        if gnames_offset is None or gobjects_offset is None:
            raise RuntimeError("Failed to find memory offsets")
        
        self.gnames_offset = gnames_offset
        self.gobjects_offset = gobjects_offset
    
    def _init_frida(self):
        """Initialize Frida for function hooking"""
        try:
            self._frida_session = frida.attach(PROCESS_NAME)
            self._frida_script = self._frida_session.create_script(FRIDA_SCRIPT)
            self._frida_script.on('message', self._on_frida_message)
            self._frida_script.load()
            
            print("[HazeSDK] ✓ Frida initialized")
        except Exception as e:
            print(f"[HazeSDK] ⚠ Frida initialization failed: {e}")
    
    def _load_gnames(self):
        """Load GNames table"""
        import ctypes
        
        with self.perf_monitor.time_operation("load_gnames"):
            gnames_addr = self.mm.base_address + self.gnames_offset
            array_data_addr = self.mm.read_longlong(gnames_addr)
            array_count = self.mm.read_int(gnames_addr + 0x8)
            
            # Load up to 100k names (reasonable limit)
            max_names = min(array_count, 100000)
            
            for i in range(max_names):
                try:
                    entry_addr = self.mm.read_longlong(array_data_addr + i * 0x8)
                    if entry_addr == 0:
                        continue
                    
                    # Read name from entry
                    name_addr = entry_addr + 0x0018
                    name_bytes = self.mm.read_bytes(name_addr, 0x400)
                    
                    # Use ctypes.wstring_at to properly read UTF-16 wide string
                    name = ctypes.wstring_at(name_bytes)
                    
                    if name:
                        # Get index
                        index = self.mm.read_int(entry_addr + 0x0008)
                        self._gnames[index] = name
                except:
                    continue
            
            print(f"[HazeSDK] ✓ Loaded {len(self._gnames)} names")
    
    def _find_functions(self):
        """Find important function addresses and classes"""
        with self.perf_monitor.time_operation("find_functions"):
            gobjects_addr = self.mm.base_address + self.gobjects_offset
            array_data_addr = self.mm.read_longlong(gobjects_addr)
            array_count = self.mm.read_int(gobjects_addr + 0x8)
            
            # Dict to store classes (like Core.Object)
            self._static_classes = {}
            
            # Scan GObjects for functions AND classes
            max_objects = min(array_count, 100000)
            
            print(f"[HazeSDK] Scanning {max_objects} objects...")
            print(f"[HazeSDK] GObjects addr: {hex(gobjects_addr)}")
            print(f"[HazeSDK] Array data addr: {hex(array_data_addr)}")
            
            classes_found = 0
            functions_found = 0
            valid_objects = 0
            errors = 0
            
            for i in range(max_objects):
                try:
                    obj_addr = self.mm.read_longlong(array_data_addr + i * 0x8)
                    if obj_addr == 0:
                        continue
                    
                    valid_objects += 1
                    
                    # Debug first valid object
                    if valid_objects == 1:
                        print(f"[HazeSDK] First valid object at {hex(obj_addr)}")
                    
                    # Get name index
                    name_index = self.mm.read_int(obj_addr + UOBJECT_NAME)
                    name = self._gnames.get(name_index, "")
                    
                    if valid_objects == 1:
                        print(f"[HazeSDK] First object name_index: {name_index}, name: '{name}'")
                    
                    # Get class
                    class_addr = self.mm.read_longlong(obj_addr + UOBJECT_CLASS)
                    if class_addr == 0:
                        continue
                    
                    class_name_index = self.mm.read_int(class_addr + UOBJECT_NAME)
                    class_name = self._gnames.get(class_name_index, "")
                    
                    if valid_objects == 1:
                        print(f"[HazeSDK] First object class_name: '{class_name}'")
                    
                    # Build full name with hierarchy
                    full_name = self._build_full_name(obj_addr, name, class_name)
                    
                    if valid_objects <= 3:
                        print(f"[HazeSDK] Object {valid_objects}: {full_name}")
                    
                    # Store Classes (important for finding ProcessEvent!)
                    if class_name == "Class":
                        self._static_classes[full_name] = obj_addr
                        classes_found += 1
                        if "Core.Object" in full_name:
                            print(f"[HazeSDK] ✓ Found Core.Object at {hex(obj_addr)}: {full_name}")
                        # Debug: print first few classes
                        if classes_found <= 5:
                            print(f"[HazeSDK] Class: {full_name}")
                    
                    # Store Functions we need
                    elif class_name == "Function":
                        # Check if it's a function we need
                        for func_name in FUNCTION_NAMES.values():
                            if full_name == func_name:
                                self._static_functions[func_name] = obj_addr
                                functions_found += 1
                                print(f"[HazeSDK] ✓ Found function: {func_name}")
                                break
                except Exception as e:
                    errors += 1
                    # Debug first few errors
                    if errors <= 5:
                        print(f"[HazeSDK] Error at index {i}: {type(e).__name__}: {e}")
                    continue
            
            print(f"[HazeSDK] Scan complete: {valid_objects} valid objects, {errors} errors")
            
            print(f"[HazeSDK] ✓ Found {len(self._static_classes)} classes, {len(self._static_functions)} functions")
    
    def _build_full_name(self, obj_addr: int, name: str, class_name: str = "") -> str:
        """Build full object name including outer hierarchy"""
        try:
            full_name = name
            outer_addr = self.mm.read_longlong(obj_addr + UOBJECT_OUTER)
            
            while outer_addr != 0:
                outer_name_index = self.mm.read_int(outer_addr + UOBJECT_NAME)
                outer_name = self._gnames.get(outer_name_index, "")
                full_name = f"{outer_name}.{full_name}"
                outer_addr = self.mm.read_longlong(outer_addr + UOBJECT_OUTER)
            
            # Add proper prefix based on class type
            if class_name:
                return f"{class_name} {full_name}"
            return full_name
        except:
            return name
    
    def _setup_hooks(self):
        """Setup function hooks via Frida"""
        if not self._frida_script:
            return
        
        # Get ProcessEvent address from Core.Object class
        try:
            # Find Core.Object class in static_classes
            core_object_addr = None
            for class_name, class_addr in self._static_classes.items():
                if "Core.Object" in class_name:
                    core_object_addr = class_addr
                    print(f"[HazeSDK] Using Core.Object at {hex(class_addr)}")
                    break
            
            if core_object_addr:
                # Read vtable and get ProcessEvent (index 67)
                vtable_addr = self.mm.read_longlong(core_object_addr)
                process_event_addr = self.mm.read_longlong(vtable_addr + (0x8 * 67))
                
                print(f"[HazeSDK] ProcessEvent found at {hex(process_event_addr)}")
                self._frida_script.exports.set_process_event_address(hex(process_event_addr))
            else:
                print("[HazeSDK] ✗ Core.Object not found - hooks will not work!")
        except Exception as e:
            print(f"[HazeSDK] ✗ Failed to setup ProcessEvent: {e}")
        
        # Hook key functions
        for func_key, func_name in FUNCTION_NAMES.items():
            if func_name in self._static_functions:
                try:
                    func_addr = self._static_functions[func_name]
                    
                    # Special handling for key press - need args
                    if func_key == "KEY_PRESS":
                        self._frida_script.exports.hook_function(hex(func_addr), func_name, [
                            {"index": 2, "type": "bytes", "name": "key_params", "size": 28}
                        ])
                    else:
                        self._frida_script.exports.hook_function(hex(func_addr), func_name)
                except Exception as e:
                    print(f"[HazeSDK] Failed to hook {func_name}: {e}")
    
    def _get_object_type(self, addr: int) -> str:
        """Get object type name"""
        try:
            name_index = self.mm.read_int(addr + UOBJECT_NAME)
            return self._gnames.get(name_index, "Unknown")
        except:
            return "Unknown"
    
    def _on_frida_message(self, message, data):
        """Handle Frida messages"""
        if message['type'] != 'send':
            return
        
        payload = message.get('payload', {})
        msg_type = payload.get('type')
        
        if msg_type == 'function_called':
            func_name = payload.get('name', '')
            caller_addr = int(payload.get('caller', '0x0'), 16)
            
            # Handle specific function calls
            if func_name == FUNCTION_NAMES['PLAYER_TICK'] or func_name == FUNCTION_NAMES['VIEWPORT_TICK']:
                event = Event(EventType.TICK)
                self.event_manager.fire(event)
            
            elif func_name == FUNCTION_NAMES['BOOST_PICKED_UP']:
                if caller_addr != 0:
                    location = self.mm.read_vector3(caller_addr + ACTOR_LOCATION)
                    if self._game_state:
                        self._game_state.on_boost_picked_up(location)
                
                event = Event(EventType.BOOST_PICKED_UP)
                self.event_manager.fire(event)
            
            elif func_name == FUNCTION_NAMES['BOOST_RESPAWN']:
                if caller_addr != 0:
                    location = self.mm.read_vector3(caller_addr + ACTOR_LOCATION)
                    if self._game_state:
                        self._game_state.on_boost_respawned(location)
                
                event = Event(EventType.BOOST_RESPAWNED)
                self.event_manager.fire(event)
            
            elif func_name == FUNCTION_NAMES['ROUND_ACTIVE_BEGIN']:
                event = Event(EventType.ROUND_STARTED)
                self.event_manager.fire(event)
            
            elif func_name == FUNCTION_NAMES['ROUND_ACTIVE_END']:
                event = Event(EventType.ROUND_ENDED)
                self.event_manager.fire(event)
            
            elif func_name == FUNCTION_NAMES['GAMEEVENT_BEGIN']:
                # Game started, store game event address
                self._game_event_address = caller_addr
                self._game_state = GameState(caller_addr, self.mm)
                
                event = Event(EventType.GAME_STARTED)
                self.event_manager.fire(event)
            
            elif func_name == FUNCTION_NAMES['GAMEEVENT_DESTROYED']:
                self._game_event_address = None
                self._game_state = None
                
                event = Event(EventType.GAME_ENDED)
                self.event_manager.fire(event)
            
            elif func_name == FUNCTION_NAMES['KEY_PRESS']:
                # Handle key press
                if 'key_params' in payload.get('args', {}):
                    params_hex = payload['args']['key_params']
                    
                    try:
                        # Convert hex to bytes
                        data_bytes = bytes.fromhex(params_hex)
                        
                        # Extract key name index (at offset 4, 4 bytes)
                        if len(data_bytes) >= 8:
                            fname_entry_id = int.from_bytes(data_bytes[4:8], byteorder='little')
                            key_name = self._gnames.get(fname_entry_id, "Unknown")
                            
                            # Fire key pressed event
                            event = Event(EventType.KEY_PRESSED, {'key': key_name, 'data': data_bytes})
                            self.event_manager.fire(event)
                    except Exception as e:
                        print(f"[HazeSDK] Key press error: {e}")
    
    # =================================================================
    # PUBLIC API
    # =================================================================
    
    def get_game_state(self) -> Optional[GameState]:
        """
        Get current game state.
        
        Returns:
            GameState object or None if not in game
        """
        if self._game_state:
            with self.perf_monitor.time_operation("update_game_state"):
                self._game_state.update()
        
        return self._game_state
    
    def on_tick(self, callback: Callable):
        """
        Decorator to register tick callback.
        
        Example:
            @sdk.on_tick
            def my_tick(event):
                game_state = sdk.get_game_state()
        """
        self.event_manager.subscribe(EventType.TICK, callback)
        return callback
    
    def on_event(self, event_type: EventType, callback: Callable):
        """Register event callback"""
        self.event_manager.subscribe(event_type, callback)
    
    # =================================================================
    # PERFORMANCE & DEBUGGING
    # =================================================================
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics"""
        return {
            'memory': self.mm.get_performance_stats(),
            'cache': self.mm.get_cache_stats(),
            'sdk': self.perf_monitor.get_all_stats()
        }
    
    def print_performance_summary(self):
        """Print performance summary"""
        print("\n" + "="*70)
        print("HazeSDK Performance Summary")
        print("="*70)
        
        print("\nMemory Manager:")
        self.mm.print_performance_summary()
        
        print("\nSDK Operations:")
        self.perf_monitor.print_summary()
        
        print("\nCache Statistics:")
        stats = self.mm.get_cache_stats()
        print(f"  Hits: {stats['hits']}")
        print(f"  Misses: {stats['misses']}")
        print(f"  Hit Rate: {stats['hit_rate']:.1f}%")
        print(f"  Cached Items: {stats['size']}")

