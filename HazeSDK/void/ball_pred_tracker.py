import numpy as np
from typing import List
from .util import common_values


class BallState:
    """Represents ball state at a given time"""
    def __init__(self, position=None, velocity=None, angular_velocity=None):
        self.position = position if position is not None else np.zeros(3)
        self.velocity = velocity if velocity is not None else np.zeros(3)
        self.angular_velocity = angular_velocity if angular_velocity is not None else np.zeros(3)
    
    def copy(self):
        """Create a copy of this state"""
        return BallState(
            self.position.copy(),
            self.velocity.copy(),
            self.angular_velocity.copy()
        )
    
    def matches(self, other, tolerance=10.0):
        """Check if two ball states match (within tolerance)"""
        pos_diff = np.linalg.norm(self.position - other.position)
        vel_diff = np.linalg.norm(self.velocity - other.velocity)
        return pos_diff < tolerance and vel_diff < tolerance


class BallPredTracker:
    """
    Ball prediction tracker using simplified Rocket League physics
    Similar to RocketSim's BallPredTracker but without external dependencies
    """
    
    # Physics constants (Rocket League)
    GRAVITY = -650.0  # UU/s²
    BALL_RADIUS = common_values.BALL_RADIUS
    BALL_RESTITUTION = 0.6  # Bounce coefficient
    BALL_FRICTION = 0.35  # Surface friction
    
    # Arena bounds
    SIDE_WALL_X = common_values.SIDE_WALL_X
    BACK_WALL_Y = common_values.BACK_WALL_Y
    CEILING_Z = common_values.CEILING_Z
    FLOOR_Z = 0.0
    
    def __init__(self, num_pred_ticks: int, tick_time: float = 1.0/120.0):
        """
        Initialize ball prediction tracker
        
        Args:
            num_pred_ticks: Number of ticks to predict ahead
            tick_time: Time per tick in seconds (default 1/120)
        """
        self.num_pred_ticks = num_pred_ticks
        self.tick_time = tick_time
        self.pred_data: List[BallState] = []
        self.last_update_tick_count = 0
        
    def update_pred_from_ball(self, ball_position, ball_velocity, ball_angular_velocity, 
                             current_tick_count: int):
        """
        Update prediction from current ball state
        
        Args:
            ball_position: Current ball position (x, y, z)
            ball_velocity: Current ball velocity
            ball_angular_velocity: Current ball angular velocity
            current_tick_count: Current game tick
        """
        current_state = BallState(
            np.array(ball_position, dtype=np.float32),
            np.array(ball_velocity, dtype=np.float32),
            np.array(ball_angular_velocity, dtype=np.float32)
        )
        
        ticks_since_last_update = current_tick_count - self.last_update_tick_count
        self._update_pred_manual(current_state, ticks_since_last_update)
        self.last_update_tick_count = current_tick_count
    
    def _update_pred_manual(self, current_ball_state: BallState, ticks_since_last_update: int):
        """Update prediction with optimization (like C++ version)"""
        needs_full_repred = True
        
        # Try to reuse existing prediction data
        if ticks_since_last_update < len(self.pred_data):
            if self.pred_data[ticks_since_last_update].matches(current_ball_state):
                needs_full_repred = False
                
                if ticks_since_last_update > 0:
                    # Remove old states, keep the rest
                    self.pred_data = self.pred_data[ticks_since_last_update:]
                    
                    # Predict new states to reach num_pred_ticks
                    while len(self.pred_data) < self.num_pred_ticks:
                        next_state = self._simulate_step(self.pred_data[-1])
                        self.pred_data.append(next_state)
        
        if needs_full_repred:
            self._force_update_all_pred(current_ball_state)
    
    def _force_update_all_pred(self, initial_ball_state: BallState):
        """Force full re-prediction"""
        self.pred_data = [initial_ball_state.copy()]
        
        for i in range(1, self.num_pred_ticks):
            next_state = self._simulate_step(self.pred_data[-1])
            self.pred_data.append(next_state)
    
    def _simulate_step(self, state: BallState) -> BallState:
        """
        Simulate one physics step (one tick)
        This is the equivalent of ballPredArena->Step()
        """
        new_state = state.copy()
        dt = self.tick_time
        
        # Apply gravity
        gravity_accel = np.array([0.0, 0.0, self.GRAVITY])
        new_state.velocity += gravity_accel * dt
        
        # Update position
        new_state.position += new_state.velocity * dt
        
        # Handle collisions with arena bounds
        self._handle_collisions(new_state)
        
        return new_state
    
    def _handle_collisions(self, state: BallState):
        """Handle collisions with floor, walls, and ceiling"""
        
        # Floor collision
        if state.position[2] < self.BALL_RADIUS:
            state.position[2] = self.BALL_RADIUS
            if state.velocity[2] < 0:
                state.velocity[2] = -state.velocity[2] * self.BALL_RESTITUTION
                # Apply friction
                horizontal_speed = np.sqrt(state.velocity[0]**2 + state.velocity[1]**2)
                if horizontal_speed > 0:
                    friction_factor = max(0, 1 - self.BALL_FRICTION)
                    state.velocity[0] *= friction_factor
                    state.velocity[1] *= friction_factor
        
        # Ceiling collision
        if state.position[2] > self.CEILING_Z - self.BALL_RADIUS:
            state.position[2] = self.CEILING_Z - self.BALL_RADIUS
            if state.velocity[2] > 0:
                state.velocity[2] = -state.velocity[2] * self.BALL_RESTITUTION
        
        # Side walls collision (X axis)
        if abs(state.position[0]) > self.SIDE_WALL_X - self.BALL_RADIUS:
            if state.position[0] > 0:
                state.position[0] = self.SIDE_WALL_X - self.BALL_RADIUS
            else:
                state.position[0] = -(self.SIDE_WALL_X - self.BALL_RADIUS)
            state.velocity[0] = -state.velocity[0] * self.BALL_RESTITUTION
        
        # Back walls collision (Y axis)
        if abs(state.position[1]) > self.BACK_WALL_Y - self.BALL_RADIUS:
            if state.position[1] > 0:
                state.position[1] = self.BACK_WALL_Y - self.BALL_RADIUS
            else:
                state.position[1] = -(self.BACK_WALL_Y - self.BALL_RADIUS)
            state.velocity[1] = -state.velocity[1] * self.BALL_RESTITUTION
    
    def get_ball_state_for_time(self, pred_time: float) -> BallState:
        """
        Get predicted ball state at a specific time
        
        Args:
            pred_time: Time in seconds from now
            
        Returns:
            BallState at that time
        """
        if not self.pred_data:
            # Return zero state if no prediction data
            return BallState()
        
        # Clamp index to valid range
        index = int(np.clip(pred_time / self.tick_time, 0, len(self.pred_data) - 1))
        return self.pred_data[index]
    
    def is_valid(self) -> bool:
        """Check if prediction data is valid"""
        return len(self.pred_data) > 0

