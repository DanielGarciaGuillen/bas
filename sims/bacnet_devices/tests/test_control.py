import math

from control import (
    ACTUATOR_SLEW_PCT_PER_TICK,
    COIL_MAX_DELTA_C,
    FAN_PID_KI,
    FAN_PID_KP,
    OA_DAMPER_MAX_PCT,
    OA_DAMPER_MIN_PCT,
    SAT_PID_KI,
    SAT_PID_KP,
    SAT_RESPONSE_RATE,
    PIController,
    economizer_oa_damper_pct,
    fan_curve_pressure_inwc,
    mixed_air_temp_c,
    outside_air_temp_c,
    ramp_toward,
    schedule_mode,
    split_range_valves,
    step_return_air_temp_c,
)


def test_schedule_mode_transitions():
    assert schedule_mode(6.0) == "unoccupied"
    assert schedule_mode(7.5) == "warmup"
    assert schedule_mode(8.0) == "occupied"
    assert schedule_mode(13.0) == "occupied"
    assert schedule_mode(18.0) == "unoccupied"
    assert schedule_mode(23.0) == "unoccupied"


def test_outside_air_temp_peaks_mid_afternoon_and_troughs_before_dawn():
    temps = {h: outside_air_temp_c(h) for h in range(24)}
    assert max(temps, key=temps.get) == 15
    assert min(temps, key=temps.get) == 3


def test_economizer_opens_wide_when_cooling_is_needed_and_oat_usefully_below_rat():
    assert (
        economizer_oa_damper_pct(oat_c=5.0, rat_c=22.0, fan_running=True, cooling_demand_pct=50.0)
        == OA_DAMPER_MAX_PCT
    )


def test_economizer_ignores_cold_outside_air_during_a_heating_call():
    """The bug this guards: free cooling has no business engaging just because it's
    cold outside while the loop is actually calling for heat."""
    assert (
        economizer_oa_damper_pct(oat_c=5.0, rat_c=22.0, fan_running=True, cooling_demand_pct=0.0)
        == OA_DAMPER_MIN_PCT
    )


def test_economizer_sits_at_ventilation_minimum_when_oat_too_close_to_rat():
    assert (
        economizer_oa_damper_pct(oat_c=21.5, rat_c=22.0, fan_running=True, cooling_demand_pct=50.0)
        == OA_DAMPER_MIN_PCT
    )


def test_economizer_avoids_freeze_risk_even_when_cooling_is_needed():
    assert (
        economizer_oa_damper_pct(oat_c=-10.0, rat_c=22.0, fan_running=True, cooling_demand_pct=50.0)
        == OA_DAMPER_MIN_PCT
    )


def test_economizer_closes_fully_when_fan_is_off():
    assert (
        economizer_oa_damper_pct(oat_c=5.0, rat_c=22.0, fan_running=False, cooling_demand_pct=50.0)
        == 0.0
    )


def test_mixed_air_temp_blends_by_damper_fraction():
    assert mixed_air_temp_c(oat_c=0.0, rat_c=20.0, oa_damper_pct=50.0) == 10.0
    assert mixed_air_temp_c(oat_c=0.0, rat_c=20.0, oa_damper_pct=0.0) == 20.0
    assert mixed_air_temp_c(oat_c=0.0, rat_c=20.0, oa_damper_pct=100.0) == 0.0


def test_return_air_temp_relaxes_toward_supply_air_over_time():
    rat = 22.0
    for _ in range(150):  # 150 * 60s = 9000s = 5 time constants, ~99% of the way there
        rat = step_return_air_temp_c(rat, sat_c=13.0, occupied=False, dt_s=60.0)
    assert math.isclose(rat, 13.0, abs_tol=0.5)


def test_split_range_valves_never_calls_for_heat_and_cool_at_once():
    assert split_range_valves(40.0) == (40.0, 0.0)
    assert split_range_valves(-40.0) == (0.0, 40.0)
    assert split_range_valves(0.0) == (0.0, 0.0)


def test_ramp_toward_moves_but_does_not_overshoot():
    assert ramp_toward(current=20.0, target=90.0, max_delta=5.0) == 25.0
    assert ramp_toward(current=88.0, target=90.0, max_delta=5.0) == 90.0  # clamps at target
    assert ramp_toward(current=90.0, target=20.0, max_delta=5.0) == 85.0


def test_fan_curve_pressure_rises_with_the_square_of_speed():
    assert fan_curve_pressure_inwc(fan_speed_pct=0.0) == 0.0
    assert math.isclose(fan_curve_pressure_inwc(fan_speed_pct=100.0), 2.0)
    # half speed -> a quarter of full-speed pressure, not half
    assert math.isclose(fan_curve_pressure_inwc(fan_speed_pct=50.0), 0.5)


def _simulate_sat_loop(sat_c, setpoint_c, oat_c, rat_c, ticks=900, dt_s=2.0):
    """Runs the same shape of loop as sims/bacnet_devices/main.py's update_ahu1, as a
    reusable fixture for convergence tests."""
    sat_pid = PIController(kp=SAT_PID_KP, ki=SAT_PID_KI, output_min=-100.0, output_max=100.0)
    oa_damper = OA_DAMPER_MIN_PCT
    for _ in range(ticks):
        error = setpoint_c - sat_c
        net = sat_pid.step(error, dt_s)
        heating_pct, cooling_pct = split_range_valves(net)
        oa_damper_target = economizer_oa_damper_pct(
            oat_c, rat_c, fan_running=True, cooling_demand_pct=cooling_pct
        )
        oa_damper = ramp_toward(oa_damper, oa_damper_target, max_delta=ACTUATOR_SLEW_PCT_PER_TICK)
        mixed = mixed_air_temp_c(oat_c, rat_c, oa_damper)
        coil_effect = (
            heating_pct / 100.0 * COIL_MAX_DELTA_C - cooling_pct / 100.0 * COIL_MAX_DELTA_C
        )
        target = mixed + coil_effect
        sat_c += (target - sat_c) * SAT_RESPONSE_RATE
    return sat_c


def test_pi_controller_converges_sat_to_setpoint_on_a_heating_call():
    # Setpoint well above both the starting SAT and the cold outside air: a heating
    # call the economizer must stay out of (see the "ignores cold air" test above).
    sat_c = _simulate_sat_loop(sat_c=13.0, setpoint_c=21.0, oat_c=5.0, rat_c=22.0)
    assert math.isclose(sat_c, 21.0, abs_tol=0.5)


def test_pi_controller_converges_sat_to_setpoint_on_a_cooling_call():
    # Setpoint below RAT with cool-enough outside air: the economizer should help
    # carry this one, same as a real free-cooling day would.
    sat_c = _simulate_sat_loop(sat_c=24.0, setpoint_c=18.0, oat_c=10.0, rat_c=24.0)
    assert math.isclose(sat_c, 18.0, abs_tol=0.5)


def test_fan_loop_converges_to_static_pressure_setpoint():
    """Same shape as the SAT loop test: the fan speed and the static pressure it
    produces (via the quadratic fan curve) both have to actually settle, slew-rate
    limited the same way a real VFD/damper can't jump speed instantly."""
    fan_pid = PIController(kp=FAN_PID_KP, ki=FAN_PID_KI, output_min=0.0, output_max=100.0)
    pressure, fan_speed, setpoint = 0.0, 0.0, 1.0
    for _ in range(3000):
        error = setpoint - pressure
        target_speed = fan_pid.step(error, dt_s=2.0)
        fan_speed = ramp_toward(fan_speed, target_speed, max_delta=ACTUATOR_SLEW_PCT_PER_TICK)
        pressure = fan_curve_pressure_inwc(fan_speed)
    assert math.isclose(pressure, setpoint, abs_tol=0.05)


def test_pi_controller_respects_output_bounds():
    pid = PIController(kp=1000.0, ki=1000.0, output_min=0.0, output_max=100.0)
    assert pid.step(error=50.0, dt_s=1.0) == 100.0
    pid2 = PIController(kp=1000.0, ki=1000.0, output_min=0.0, output_max=100.0)
    assert pid2.step(error=-50.0, dt_s=1.0) == 0.0
