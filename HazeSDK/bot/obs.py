import numpy as np

from .util.physics_object import PhysicsObject
from .util.game_state import GameState
from .util.player_data import PlayerData
from .util import common_values


class AdvancedObs:
    POS_COEF = 1.0 / 5000.0
    VEL_COEF = 1.0 / 2300.0
    ANG_VEL_COEF = 1.0 / 3.0

    def _add_player_to_obs(self, obs_list: list, player: PlayerData, inverted: bool, ball_phys: PhysicsObject):
        phys = player.inverted_car_data if inverted else player.car_data

        # Position
        obs_list.extend(list(phys.position * self.POS_COEF))

        # Orientation axes: forward, up
        rot = phys.rotation_mtx()
        forward = rot[:, 0]
        up = rot[:, 2]
        obs_list.extend(list(forward))
        obs_list.extend(list(up))

        # Velocities
        obs_list.extend(list(phys.linear_velocity * self.VEL_COEF))
        obs_list.extend(list(phys.angular_velocity * self.ANG_VEL_COEF))

        # Local angular velocity = R^T * angVel
        local_ang = rot.T @ phys.angular_velocity
        obs_list.extend(list(local_ang * self.ANG_VEL_COEF))

        # Local ball pos/vel relative to car
        rel_pos = ball_phys.position - phys.position
        rel_vel = ball_phys.linear_velocity - phys.linear_velocity
        local_rel_pos = rot.T @ rel_pos
        local_rel_vel = rot.T @ rel_vel
        obs_list.extend(list(local_rel_pos * self.POS_COEF))
        obs_list.extend(list(local_rel_vel * self.VEL_COEF))

        # Discrete flags / scalars
        obs_list.append(float(player.boost_amount))
        obs_list.append(1.0 if player.on_ground else 0.0)
        # Has flip or jump
        has_flip_or_jump = (player.has_flip or getattr(player, 'has_jump', False))
        obs_list.append(1.0 if has_flip_or_jump else 0.0)
        obs_list.append(1.0 if player.is_demoed else 0.0)
        # hasJumped (to detect flip resets)
        obs_list.append(1.0 if getattr(player, 'has_jumped', False) else 0.0)

    def build_obs(self, player: PlayerData, state: GameState, prev_action: np.ndarray) -> np.ndarray:
        obs = []

        inverted = player.team_num == 1  # ORANGE

        ball = state.inverted_ball if inverted else state.ball
        pads = state.get_boost_pads(inverted)
        pad_timers = state.get_boost_pad_timers(inverted)

        # Ball global features
        obs.extend(list(ball.position * self.POS_COEF))
        obs.extend(list(ball.linear_velocity * self.VEL_COEF))
        obs.extend(list(ball.angular_velocity * self.ANG_VEL_COEF))

        # Previous action (8 dims)
        if prev_action is None:
            prev_action = np.zeros(8, dtype=np.float32)
        obs.extend(list(prev_action.astype(np.float32)))

        # Boost pad features blended with timers
        amount = common_values.BOOST_LOCATIONS_AMOUNT
        for i in range(amount):
            if pads[i] >= 0.5:
                obs.append(1.0)
            else:
                # 1 / (1 + timer) approaches 1 as it becomes available
                t = float(pad_timers[i]) if i < len(pad_timers) else 0.0
                obs.append(1.0 / (1.0 + t))

        # Self
        self._add_player_to_obs(obs, player, inverted, ball)

        # For 1v1: exactly one opponent appended. If none, pad with zeros.
        # Find first opponent
        opponent_added = False
        for other in state.players:
            if other.car_id == player.car_id:
                continue
            if other.team_num != player.team_num:
                self._add_player_to_obs(obs, other, inverted, ball)
                opponent_added = True
                break

        if not opponent_added:
            # Pad with zeros for opponent feature size (29)
            obs.extend([0.0] * 29)

        return np.asarray(obs, dtype=np.float32)
