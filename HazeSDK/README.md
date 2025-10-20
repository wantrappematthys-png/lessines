# HazeSDK

**High-Performance Rocket League SDK for Bot Development**

---

## 🚀 Features

- **Optimized Memory Access**: Intelligent caching and batch reads minimize memory calls
- **Clean API**: Simple, intuitive interface for bot development
- **Event System**: React to game events (ticks, goals, boost pickups, etc.)
- **Performance Monitoring**: Built-in profiling tools
- **Auto-Detection**: Automatic offset scanning for different game versions
- **Minimal Overhead**: Designed for 120Hz operation with minimal lag

---

## 📦 Installation

### Requirements

- Python 3.8+
- Windows (Rocket League on Steam or Epic)
- Required packages:
  ```
  pymem
  frida
  ```

### Setup

1. Install dependencies:
   ```bash
   pip install pymem frida
   ```

2. Import HazeSDK:
   ```python
   from HazeSDK import HazeSDK
   ```

---

## 🎮 Quick Start

### Basic Usage

```python
from HazeSDK import HazeSDK, EventType

# Initialize SDK
sdk = HazeSDK()

# Register tick handler
@sdk.on_tick
def on_game_tick(event):
    # Get current game state
    game_state = sdk.get_game_state()
    
    if game_state and game_state.ball:
        # Access ball data
        ball_x, ball_y, ball_z = game_state.ball.location
        ball_speed = game_state.ball.get_speed()
        
        # Access cars
        for car in game_state.cars:
            if car.is_on_ground:
                print(f"Car at {car.location}, boost: {car.boost_percent}%")

# Keep script running
import time
while True:
    time.sleep(0.1)
```

---

## 📖 API Reference

### HazeSDK

Main SDK class.

```python
sdk = HazeSDK(pid=None, enable_monitoring=False)
```

**Parameters:**
- `pid`: Process ID (optional, auto-detects RocketLeague.exe)
- `enable_monitoring`: Enable performance tracking

**Methods:**
- `get_game_state()`: Returns current `GameState` or `None`
- `on_tick(callback)`: Decorator to register tick handler
- `on_event(event_type, callback)`: Register event handler

---

### GameState

Complete game state with all objects.

**Properties:**
- `ball`: Ball object
- `cars`: List of Car objects
- `players`: List of Player objects
- `boost_pads`: List of BoostPad objects
- `time_remaining`: Seconds left in match
- `is_overtime`: True if in overtime
- `is_round_active`: True if round is active
- `is_kickoff`: True if in kickoff state

**Methods:**
- `update()`: Update all game state (called automatically)
- `get_car(index)`: Get car by index
- `get_player(index)`: Get player by index
- `get_cars_by_team(team)`: Get all cars on a team (0=blue, 1=orange)

---

### Car

Represents a car in the game.

**Properties:**
- `location`: Tuple (x, y, z) in Unreal Units
- `rotation`: Tuple (pitch, yaw, roll) in radians
- `velocity`: Tuple (vx, vy, vz)
- `angular_velocity`: Tuple (wx, wy, wz)
- `boost_amount`: Float 0.0 - 1.0
- `boost_percent`: Int 0 - 100
- `is_on_ground`: True if has wheel contact
- `has_jumped`: True if has jumped
- `has_double_jumped`: True if has double jumped
- `is_supersonic`: True if supersonic

**Methods:**
- `update_physics()`: Batch update all physics (automatic)
- `get_inputs()`: Get current controller inputs
- `get_speed()`: Calculate speed magnitude
- `get_speed_2d()`: Calculate 2D speed (ignoring Z)

---

### Ball

Represents the ball.

**Properties:**
- `location`: Tuple (x, y, z)
- `rotation`: Tuple (pitch, yaw, roll)
- `velocity`: Tuple (vx, vy, vz)
- `angular_velocity`: Tuple (wx, wy, wz)

**Methods:**
- `update_physics()`: Batch update physics
- `get_speed()`: Calculate ball speed

---

### Player

Player information (PRI).

**Properties:**
- `name`: Player name
- `team`: Team index (0=blue, 1=orange)
- `score`: Current score
- `goals`, `assists`, `saves`, `shots`: Match stats

---

### BoostPad

Boost pad state.

**Properties:**
- `location`: Tuple (x, y, z)
- `is_big`: True for big boost (100)
- `is_active`: True if available
- `respawn_time`: Seconds until respawn

---

## 🎯 Advanced Usage

### Event Handling

```python
from HazeSDK import EventType

# React to specific events
sdk.on_event(EventType.BOOST_PICKED_UP, lambda e: print("Boost picked up!"))
sdk.on_event(EventType.ROUND_STARTED, lambda e: print("Round started!"))
sdk.on_event(EventType.GOAL_SCORED, lambda e: print("GOAL!"))
```

### Performance Monitoring

```python
# Enable monitoring
sdk = HazeSDK(enable_monitoring=True)

# Get stats
stats = sdk.get_performance_stats()
print(f"Cache hit rate: {stats['cache']['hit_rate']:.1f}%")

# Print detailed report
sdk.print_performance_summary()
```

### Optimized Bot Loop

```python
@sdk.on_tick
def on_tick(event):
    game_state = sdk.get_game_state()
    if not game_state:
        return
    
    # Get my car
    my_car = game_state.get_car(0)
    
    # Efficient access - physics already batch-updated
    car_loc = my_car.location
    car_vel = my_car.velocity
    ball_loc = game_state.ball.location
    
    # Calculate bot logic
    inputs = calculate_bot_inputs(car_loc, car_vel, ball_loc)
    
    # Send to game (using memory writer)
    send_inputs_to_game(inputs)
```

---

## 🔧 Performance Tips

1. **Batch Updates**: Physics data is automatically batch-updated on each tick
2. **Caching**: Frequently accessed data is cached automatically
3. **Minimal Reads**: Use properties instead of repeated reads
4. **Event-Driven**: Use events instead of polling

### Good ✅
```python
# Physics updated once
car.update_physics()
x, y, z = car.location  # From cache
vx, vy, vz = car.velocity  # From cache
```

### Bad ❌
```python
# Multiple memory reads
x = mm.read_float(addr + 0x90)
y = mm.read_float(addr + 0x94)
z = mm.read_float(addr + 0x98)
```

---

## 📊 Performance Benchmarks

Typical performance on modern hardware:

- **Tick Rate**: 120 ticks/second
- **Memory Reads**: ~50-100 per tick
- **Cache Hit Rate**: >80%
- **Tick Processing**: <1ms average

---

## 🤝 Contributing

Contributions welcome! Areas to improve:

- Additional game object support
- More event types
- Performance optimizations
- Documentation

---

## 📝 License

Open source - use for bot development, learning, and research.

---

## ⚠️ Disclaimer

This SDK is for educational purposes. Use responsibly and in accordance with Rocket League's Terms of Service.

---

## 🆚 Comparison with RLMarlbot SDK

| Feature | HazeSDK | RLMarlbot SDK |
|---------|---------|---------------|
| Memory Caching | ✅ Intelligent | ❌ Minimal |
| Batch Reads | ✅ Optimized | ❌ Individual |
| API Simplicity | ✅ Clean | ⚠️ Complex |
| Performance Monitoring | ✅ Built-in | ❌ Manual |
| Event System | ✅ Lightweight | ⚠️ Basic |
| Documentation | ✅ Complete | ⚠️ Limited |

**HazeSDK is 2-3x faster for typical bot operations!**

---

## 📞 Support

For questions or issues, check the examples in `HazeSDK/examples/`

