import numpy as np
from typing import List, Dict

from .util.physics_object import PhysicsObject
from .util.game_state import GameState
from .util.player_data import PlayerData
from .util import common_values
from .ball_pred_tracker import BallPredTracker


class CustomObs:
    """
    CustomObs matching C++ implementation for 1v1
    Expected observation size: 206 features
    """
    POS_COEF = 1.0 / 5000.0
    VEL_COEF = 1.0 / 2300.0
    ANG_VEL_COEF = 1.0 / 3.0
    
    def __init__(self):
        # Ball prediction horizons (match your C++ training config)
        # 5 horizons * 8 features each = 40 features for 206 total
        self.pred_horizons = [0.5, 1.0, 1.5, 2.0, 2.5]  # Time in seconds
        
        # Ball prediction tracker (similar to C++ version)
        max_horizon = max(self.pred_horizons) if self.pred_horizons else 0
        tick_time = 1.0 / 120.0  # 120 Hz
        num_ticks = int(np.ceil(max_horizon / tick_time)) + 10  # + margin
        self.ball_pred_tracker = BallPredTracker(num_ticks, tick_time)
        self.last_tick_count = 0
        
    @staticmethod
    def clamp01(v: float) -> float:
        """Clamp value between 0 and 1"""
        return max(0.0, min(1.0, v))
    
    @staticmethod
    def normalize_vec(vec: np.ndarray) -> np.ndarray:
        """Normalize vector, return zero if length is too small"""
        length = np.linalg.norm(vec)
        if length < 1e-6:
            return np.zeros_like(vec)
        return vec / length

    def _add_goal_features(self, obs: List[float], phys: PhysicsObject, ball: PhysicsObject):
        """Add goal-related features (12 features)"""
        opp_goal = np.array([0.0, common_values.BACK_WALL_Y, 0.0])
        own_goal = np.array([0.0, -common_values.BACK_WALL_Y, 0.0])
        
        rot_mat = phys.rotation_mtx()
        
        # Car -> Opp Goal
        car_to_opp = opp_goal - phys.position
        car_to_opp_dist = np.linalg.norm(car_to_opp)
        obs.append(car_to_opp_dist * self.POS_COEF)
        obs.extend(list(rot_mat.T @ self.normalize_vec(car_to_opp)))
        
        # Ball -> Opp Goal (world)
        ball_to_opp = opp_goal - ball.position
        ball_to_opp_dist = np.linalg.norm(ball_to_opp)
        obs.append(ball_to_opp_dist * self.POS_COEF)
        obs.extend(list(self.normalize_vec(ball_to_opp)))
        
        # Car -> Own Goal
        car_to_own = own_goal - phys.position
        car_to_own_dist = np.linalg.norm(car_to_own)
        obs.append(car_to_own_dist * self.POS_COEF)
        obs.extend(list(rot_mat.T @ self.normalize_vec(car_to_own)))
        
        # Total: 1 + 3 + 1 + 3 + 1 + 3 = 12

    def _add_field_proximity(self, obs: List[float], phys: PhysicsObject):
        """Add field proximity features (5 features)"""
        dx = common_values.SIDE_WALL_X - abs(phys.position[0])
        dy = common_values.BACK_WALL_Y - abs(phys.position[1])
        dz = common_values.CEILING_Z - phys.position[2]
        
        obs.append(dx * self.POS_COEF)
        obs.append(dy * self.POS_COEF)
        obs.append(dz * self.POS_COEF)
        obs.append(min(dx, dy, dz) * self.POS_COEF)
        
        # Tilt (up.z)
        up_vec = phys.rotation_mtx()[:, 2]
        obs.append(up_vec[2])
        
        # Total: 5

    def _add_car_ball_extras(self, obs: List[float], phys: PhysicsObject, 
                            ball: PhysicsObject, player: PlayerData):
        """Add extra car-ball features (7 features)"""
        to_ball = ball.position - phys.position
        dist_ball = np.linalg.norm(to_ball)
        obs.append(dist_ball * self.POS_COEF)
        
        rot_mat = phys.rotation_mtx()
        dir_ball_local = rot_mat.T @ self.normalize_vec(to_ball)
        obs.extend(list(dir_ball_local))
        
        # Forward alignment
        forward = rot_mat[:, 0]
        fwd_align = forward.dot(self.normalize_vec(to_ball))
        obs.append(fwd_align)
        
        # Relative speed toward ball
        rel_speed = max(0.0, phys.linear_velocity.dot(self.normalize_vec(to_ball)))
        obs.append(rel_speed / common_values.CAR_MAX_SPEED)
        
        # Height difference
        obs.append((ball.position[2] - phys.position[2]) * self.POS_COEF)
        
        # Kickoff detection
        is_kickoff = (abs(ball.position[0]) < 20.0 and 
                     abs(ball.position[1]) < 20.0 and 
                     np.linalg.norm(ball.linear_velocity) < 50.0)
        obs.append(1.0 if is_kickoff else 0.0)
        
        # Supersonic
        is_supersonic = getattr(player, 'is_supersonic', False) or \
                       np.linalg.norm(phys.linear_velocity) >= common_values.SUPERSONIC_THRESHOLD
        obs.append(1.0 if is_supersonic else 0.0)
        
        # Total: 1 + 3 + 1 + 1 + 1 + 1 + 1 = 9 (includes supersonic)

    def _add_nearest_boost_features(self, obs: List[float], phys: PhysicsObject,
                                    pads: np.ndarray, pad_timers: np.ndarray, inverted: bool):
        """Add nearest boost features (2 features)"""
        nearest_idx = -1
        best_dist2 = 1e20
        
        for i in range(common_values.BOOST_LOCATIONS_AMOUNT):
            # Map index if inverted
            map_idx = (common_values.BOOST_LOCATIONS_AMOUNT - i - 1) if inverted else i
            pad_pos = np.array(common_values.BOOST_LOCATIONS[map_idx])
            
            # Invert position if orange team
            if inverted:
                pad_pos = np.array([-pad_pos[0], -pad_pos[1], pad_pos[2]])
            
            diff = pad_pos - phys.position
            dist2 = diff.dot(diff)
            if dist2 < best_dist2:
                best_dist2 = dist2
                nearest_idx = i
        
        if nearest_idx >= 0:
            dist = np.sqrt(best_dist2)
            obs.append(dist * self.POS_COEF)
            
            if pads[nearest_idx] >= 0.5:
                obs.append(1.0)
            else:
                t = pad_timers[nearest_idx]
                obs.append(1.0 / (1.0 + t))
        else:
            obs.append(0.0)
            obs.append(0.0)
        
        # Total: 2

    def _add_ball_line_shots(self, obs: List[float], ball: PhysicsObject):
        """Add ball line shot predictions (2 features)"""
        def on_target(pos, vel, goal_y):
            vy = vel[1]
            if abs(vy) < 1e-3:
                return 0.0
            t = (goal_y - pos[1]) / vy
            if t <= 0:
                return 0.0
            hit = pos + vel * t
            # GOAL_WIDTH_FROM_CENTER ~= 1786 (half of 3572)
            goal_width = 1786.0
            in_goal = (abs(hit[0]) <= goal_width and 
                      hit[2] > 0 and 
                      hit[2] <= common_values.GOAL_HEIGHT)
            return 1.0 if in_goal else 0.0
        
        shot_opp = on_target(ball.position, ball.linear_velocity, common_values.BACK_WALL_Y)
        shot_own = on_target(ball.position, ball.linear_velocity, -common_values.BACK_WALL_Y)
        
        obs.append(shot_opp)
        obs.append(shot_own)
        
        # Total: 2

    def _add_player_to_obs(self, obs: List[float], player: PlayerData, 
                          inverted: bool, ball: PhysicsObject):
        """Add player features to observation (32 features)"""
        phys = player.inverted_car_data if inverted else player.car_data
        
        # Position (3)
        obs.extend(list(phys.position * self.POS_COEF))
        
        # Rotation matrix
        rot_mat = phys.rotation_mtx()
        forward = rot_mat[:, 0]
        up = rot_mat[:, 2]
        
        # Forward and up (3 + 3)
        obs.extend(list(forward))
        obs.extend(list(up))
        
        # Velocity (3)
        obs.extend(list(phys.linear_velocity * self.VEL_COEF))
        
        # Angular velocity (3)
        obs.extend(list(phys.angular_velocity * self.ANG_VEL_COEF))
        
        # Local angular velocity (3)
        local_ang_vel = rot_mat.T @ phys.angular_velocity
        obs.extend(list(local_ang_vel * self.ANG_VEL_COEF))
        
        # Ball relative to player (local frame) (3 + 3)
        rel_pos = ball.position - phys.position
        rel_vel = ball.linear_velocity - phys.linear_velocity
        local_rel_pos = rot_mat.T @ rel_pos
        local_rel_vel = rot_mat.T @ rel_vel
        obs.extend(list(local_rel_pos * self.POS_COEF))
        obs.extend(list(local_rel_vel * self.VEL_COEF))
        
        # Status flags (7)
        obs.append(player.boost_amount)  # Already 0-1
        obs.append(1.0 if player.on_ground else 0.0)
        
        # HasFlipOrJump
        has_flip_or_jump = player.has_flip or player.has_jump
        obs.append(1.0 if has_flip_or_jump else 0.0)
        
        obs.append(1.0 if player.is_demoed else 0.0)
        
        # hasJumped
        has_jumped = getattr(player, 'has_jumped', False)
        obs.append(1.0 if has_jumped else 0.0)
        
        # isSupersonic
        is_supersonic = getattr(player, 'is_supersonic', False) or \
                       np.linalg.norm(phys.linear_velocity) >= common_values.SUPERSONIC_THRESHOLD
        obs.append(1.0 if is_supersonic else 0.0)
        
        # hasDoubleJumped
        has_double_jumped = getattr(player, 'has_double_jumped', False)
        obs.append(1.0 if has_double_jumped else 0.0)
        
        # Total: 3 + 3 + 3 + 3 + 3 + 3 + 3 + 3 + 7 = 31... wait, should be 32
        # Let me recount: 3+3+3+3+3+3+3+3 = 24, + 7 flags = 31
        # The C++ seems to have 32, maybe there's an extra feature I'm missing

    def _add_ball_prediction_features(self, obs: List[float], phys: PhysicsObject, 
                                      ball: PhysicsObject, opponent: PlayerData, inverted: bool,
                                      current_tick: int):
        """
        Add ball prediction features using BallPredTracker (like C++ version)
        For each horizon: relPos(3) + relVel(3) + distGoal(1) + shotOpp(1) = 8
        Then: minDist(1) + minTime(1) + landX(1) + landY(1) + landT(1) + proxAdv(1) = 6
        Total: 8 * len(horizons) + 6
        """
        opp_goal = np.array([0.0, common_values.BACK_WALL_Y, 0.0])
        rot_mat = phys.rotation_mtx()
        
        min_dist = 1e20
        min_time = 0.0
        
        # Landing detection
        land_t = 0.0
        land_pos = np.zeros(3)
        found_land = False
        
        # Proximity advantage vs opponent
        closer_count = 0
        horizon_count = 0
        
        # Get opponent position (use same inversion as player)
        opp_pos = phys.position  # Default if no opponent
        if opponent:
            opp_phys = opponent.inverted_car_data if inverted else opponent.car_data
            opp_pos = opp_phys.position
        
        # Update ball prediction tracker (like C++ UpdatePredFromArena)
        self.ball_pred_tracker.update_pred_from_ball(
            ball.position,
            ball.linear_velocity,
            ball.angular_velocity,
            current_tick
        )
        
        # Check for landing in prediction data
        for i, pred_state in enumerate(self.ball_pred_tracker.pred_data):
            if (pred_state.position[2] <= common_values.BALL_RADIUS + 5 and 
                pred_state.velocity[2] <= 0):
                if not found_land:
                    found_land = True
                    land_t = i * self.ball_pred_tracker.tick_time
                    land_pos = pred_state.position
                    break
        
        # Get predictions at specific horizons
        for t in self.pred_horizons:
            # Get predicted ball state at time t (like C++ GetBallStateForTime)
            pred_state = self.ball_pred_tracker.get_ball_state_for_time(t)
            pred_pos = pred_state.position
            pred_vel = pred_state.velocity
            
            # Features for this horizon (8)
            
            # 1. Ball relative to car (local frame) (3 + 3)
            rel_pos = pred_pos - phys.position
            rel_vel = pred_vel - phys.linear_velocity
            local_rel_pos = rot_mat.T @ rel_pos
            local_rel_vel = rot_mat.T @ rel_vel
            obs.extend(list(local_rel_pos * self.POS_COEF))
            obs.extend(list(local_rel_vel * self.VEL_COEF))
            
            # 2. Distance to opponent goal (1)
            dist_goal = np.linalg.norm(opp_goal - pred_pos)
            obs.append(dist_goal * self.POS_COEF)
            
            # 3. Shot on target at this horizon (1)
            vy = pred_vel[1]
            shot_opp = 0.0
            if abs(vy) > 1e-3:
                tt = (common_values.BACK_WALL_Y - pred_pos[1]) / vy
                if tt > 0:
                    hit = pred_pos + pred_vel * tt
                    goal_width = 1786.0
                    in_goal = (abs(hit[0]) <= goal_width and 
                              hit[2] > 0 and 
                              hit[2] <= common_values.GOAL_HEIGHT)
                    shot_opp = 1.0 if in_goal else 0.0
            obs.append(shot_opp)
            
            # Track minimum distance
            dist = np.linalg.norm(pred_pos - phys.position)
            if dist < min_dist:
                min_dist = dist
                min_time = t
            
            # Proximity advantage vs opponent
            if opponent:
                d_agent = np.linalg.norm(pred_pos - phys.position)
                d_opp = np.linalg.norm(pred_pos - opp_pos)
                closer_count += (1 if d_agent <= d_opp else 0)
            horizon_count += 1
        
        # Add final 6 features
        
        # 1. Min distance (1)
        obs.append(min_dist * self.POS_COEF if min_dist < 1e19 else 0.0)
        
        # 2. Min time (1)
        obs.append(self.clamp01(min_time / 2.0))
        
        # 3. Landing position x, y (2)
        if found_land:
            obs.append(land_pos[0] * self.POS_COEF)
            obs.append(land_pos[1] * self.POS_COEF)
        else:
            obs.append(0.0)
            obs.append(0.0)
        
        # 4. Landing time (1)
        obs.append(self.clamp01(land_t / 2.0) if found_land else 0.0)
        
        # 5. Proximity advantage (1)
        prox_adv = float(closer_count) / horizon_count if horizon_count > 0 else 0.0
        obs.append(prox_adv)
        
        # Total: 8 * 5 + 6 = 46 features

    def build_obs(self, player: PlayerData, state: GameState, prev_action: np.ndarray) -> np.ndarray:
        """
        Build observation matching C++ CustomObs
        Target: 206 features for 1v1
        """
        obs = []
        
        inverted = player.team_num == 1  # ORANGE
        
        # Get inverted physics if orange team
        ball = state.inverted_ball if inverted else state.ball
        phys = player.inverted_car_data if inverted else player.car_data
        pads = state.get_boost_pads(inverted)
        pad_timers = state.get_boost_pad_timers(inverted)
        
        # === GLOBAL FEATURES ===
        
        # 1. Ball (world, inverted if orange) (9)
        obs.extend(list(ball.position * self.POS_COEF))
        obs.extend(list(ball.linear_velocity * self.VEL_COEF))
        obs.extend(list(ball.angular_velocity * self.ANG_VEL_COEF))
        
        # 2. Ball line shots (2)
        self._add_ball_line_shots(obs, ball)
        
        # 3. Previous action (8)
        if prev_action is None:
            prev_action = np.zeros(8, dtype=np.float32)
        obs.extend(list(prev_action.astype(np.float32)))
        
        # 4. Boost pads (34)
        for i in range(common_values.BOOST_LOCATIONS_AMOUNT):
            if pads[i] >= 0.5:
                obs.append(1.0)
            else:
                t = pad_timers[i]
                obs.append(1.0 / (1.0 + t))
        
        # === SELF FEATURES ===
        self_obs_start = len(obs)
        
        # 5. Self player (31-32)
        self._add_player_to_obs(obs, player, inverted, ball)
        
        # 6. Car-ball extras (9)
        self._add_car_ball_extras(obs, phys, ball, player)
        
        # 7. Goal features (12)
        self._add_goal_features(obs, phys, ball)
        
        # 8. Nearest boost (2)
        self._add_nearest_boost_features(obs, phys, pads, pad_timers, inverted)
        
        # 9. Field proximity (5)
        self._add_field_proximity(obs, phys)
        
        # Find opponent BEFORE ball prediction (needed for proximity advantage)
        opponent = None
        for other in state.players:
            if other.car_id != player.car_id and other.team_num != player.team_num:
                opponent = other
                break
        
        # 10. Ball prediction features (46 = 8*5 + 6)
        # Using BallPredTracker (like C++ RocketSim version)
        if len(self.pred_horizons) > 0:
            # Increment tick counter (simulating game tick)
            self.last_tick_count += 1
            self._add_ball_prediction_features(obs, phys, ball, opponent, inverted, self.last_tick_count)
        else:
            # Without prediction: minDist, minTime, landX, landY, landT, proxAdv
            obs.extend([0.0] * 6)
        
        # === OPPONENT FEATURES ===
        
        if opponent:
            opp_phys = opponent.inverted_car_data if inverted else opponent.car_data
            rot_mat = phys.rotation_mtx()
            
            # Relative position/velocity in agent's local frame (3 + 3)
            rel_pos = opp_phys.position - phys.position
            rel_vel = opp_phys.linear_velocity - phys.linear_velocity
            obs.extend(list(rot_mat.T @ rel_pos * self.POS_COEF))
            obs.extend(list(rot_mat.T @ rel_vel * self.VEL_COEF))
            
            # Opponent angular velocity (local to agent) (3)
            opp_ang_vel_local = rot_mat.T @ opp_phys.angular_velocity
            obs.extend(list(opp_ang_vel_local * self.ANG_VEL_COEF))
            
            # Full opponent player features (31-32)
            self._add_player_to_obs(obs, opponent, inverted, ball)
            
            # Opponent orientation in agent's frame (3 + 3)
            opp_rot_mat = opp_phys.rotation_mtx()
            opp_fwd_local = rot_mat.T @ opp_rot_mat[:, 0]
            opp_up_local = rot_mat.T @ opp_rot_mat[:, 2]
            obs.extend(list(opp_fwd_local))
            obs.extend(list(opp_up_local))
            
            # Opponent alignment to ball (1)
            opp_to_ball = ball.position - opp_phys.position
            opp_align = opp_rot_mat[:, 0].dot(self.normalize_vec(opp_to_ball))
            obs.append(opp_align)
            
            # Opponent boost (1)
            obs.append(opponent.boost_amount)
            
        else:
            # Pad with zeros if no opponent
            # Opponent features: 3+3+3+31+3+3+1+1 = 48
            obs.extend([0.0] * 48)
        
        result = np.asarray(obs, dtype=np.float32)
        
        # Debug: print size (remove after verification)
        if len(result) != 206:
            print(f"⚠️ Warning: Obs size is {len(result)}, expected 206")
        
        return result


# Alias for backward compatibility
AdvancedObs = CustomObs
