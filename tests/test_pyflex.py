#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pyflex test suite.

Run with pytest.

:copyright:
    Lion Krischer (krischer@geophysik.uni-muenchen.de), 2014
:license:
    GNU General Public License, Version 3
    (http://www.gnu.org/copyleft/gpl.html)
"""
import inspect
import numpy as np
import obspy
import os

import pyflex

# Most generic way to get the data folder path.
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(
    inspect.getfile(inspect.currentframe()))), "data")

# Prepare data to be able to use it in all tests.
OBS_DATA = obspy.read(os.path.join(
    DATA_DIR, "1995.122.05.32.16.0000.II.ABKT.00.LHZ.D.SAC"))
SYNTH_DATA = obspy.read(os.path.join(DATA_DIR, "ABKT.II.LHZ.semd.sac"))

# Preprocess it.
OBS_DATA.detrend("linear")
OBS_DATA.taper(max_percentage=0.05, type="hann")
OBS_DATA.filter("bandpass", freqmin=1.0 / 150.0, freqmax=1.0 / 50.0,
                corners=4, zerophase=True)
SYNTH_DATA.detrend("linear")
SYNTH_DATA.taper(max_percentage=0.05, type="hann")
SYNTH_DATA.filter("bandpass", freqmin=1.0 / 150.0, freqmax=1.0 / 50.0,
                  corners=4, zerophase=True)


def test_window_selection():
    """
    This WILL need to be adjusted if any part of the algorithm changes!

    The settings for this test are more or less the same as for the test
    data example in the original FLEXWIN package.
    """
    config = pyflex.Config(
        min_period=50.0, max_period=150.0,
        stalta_waterlevel=0.08, tshift_acceptance_level=15.0,
        dlna_acceptance_level=1.0, cc_acceptance_level=0.80,
        c_0=0.7, c_1=4.0, c_2=0.0, c_3a=1.0, c_3b=2.0, c_4a=3.0, c_4b=10.0)

    windows = pyflex.select_windows(OBS_DATA, SYNTH_DATA, config)
    assert len(windows) == 7

    assert [_i.left for _i in windows] == [1551, 2221, 2709, 2960, 3353, 3609,
                                           3983]
    assert [_i.right for _i in windows] == [1985, 2709, 2960, 3172, 3609, 3920,
                                            4442]
    np.testing.assert_allclose(
        np.array([_i.max_cc_value for _i in windows]),
        np.array([0.95740629373181685, 0.96646803651993862, 0.9633571597878805,
                  0.98249546895396034, 0.96838753962768898,
                  0.88501979275369003, 0.82529382012185848]))
    assert [_i.cc_shift for _i in windows] == [-3, 0, -5, -5, -6, 4, -9]
    np.testing.assert_allclose(
        np.array([_i.dlnA for _i in windows]),
        np.array([0.074690084388978839, 0.12807961376836777,
                  -0.19276977567364437, 0.18556340842688038,
                  0.093674448597561411, -0.11885913254077075,
                  -0.63865703707265198]))

    # Assert the phases of the first window.
    assert sorted([_i["phase_name"] for _i in windows[0].phase_arrivals]) == \
        [u'PKPdf', u'PKSdf', u'PKiKP', u'PP', u'SKPdf', u'SKiKP', u'pPKPdf',
         u'pPKiKP', u'sPKPdf', u'sPKiKP']


def test_cc_config_setting():
    """
    Make sure setting the CC threshold does something.
    """
    config = pyflex.Config(
        min_period=50.0, max_period=150.0,
        stalta_waterlevel=0.08, tshift_acceptance_level=15.0,
        dlna_acceptance_level=1.0, cc_acceptance_level=0.95,
        c_0=0.7, c_1=4.0, c_2=0.0, c_3a=1.0, c_3b=2.0, c_4a=3.0, c_4b=10.0)

    windows = pyflex.select_windows(OBS_DATA, SYNTH_DATA, config)
    assert np.all(np.array([_i.max_cc_value for _i in windows]) >= 0.95)


def test_custom_weight_function():
    """
    Test the custom weight function. Set the weight of every window with a
    CC of smaller then 95 to 0.0.
    """
    def weight_function(win):
        if win.max_cc_value < 0.95:
            return 0.0
        else:
            return 10.0

    config = pyflex.Config(
        min_period=50.0, max_period=150.0,
        stalta_waterlevel=0.08, tshift_acceptance_level=15.0,
        dlna_acceptance_level=1.0, cc_acceptance_level=0.80,
        c_0=0.7, c_1=4.0, c_2=0.0, c_3a=1.0, c_3b=2.0, c_4a=3.0, c_4b=10.0,
        window_weight_fct=weight_function)

    windows = pyflex.select_windows(OBS_DATA, SYNTH_DATA, config)
    assert np.all(np.array([_i.max_cc_value for _i in windows]) >= 0.95)

    # Not setting it will result in the default value.
    config.window_weight_fct = None
    windows = pyflex.select_windows(OBS_DATA, SYNTH_DATA, config)
    assert False == \
        np.all(np.array([_i.max_cc_value for _i in windows]) >= 0.95)


def test_runs_without_event_information(recwarn):
    """
    Make sure it runs without event information. Some things will not work
    but it will at least not crash.
    """
    config = pyflex.Config(
        min_period=50.0, max_period=150.0,
        stalta_waterlevel=0.08, tshift_acceptance_level=15.0,
        dlna_acceptance_level=1.0, cc_acceptance_level=0.80,
        c_0=0.7, c_1=4.0, c_2=0.0, c_3a=1.0, c_3b=2.0, c_4a=3.0, c_4b=10.0)

    obs = OBS_DATA[0].copy()
    syn = SYNTH_DATA[0].copy()

    # Remove the sac header information.
    del obs.stats.sac
    del syn.stats.sac

    recwarn.clear()
    windows = pyflex.select_windows(obs, syn, config)

    # This will actually result in a bunch more windows as before. So it
    # is always a good idea to specify the event and station information!
    assert len(windows) == 12

    assert len(recwarn.list) == 1
    w = recwarn.list[0]
    assert w.category == pyflex.PyflexWarning
    assert "Event and/or station information is not available".lower() in \
        str(w.message).lower()

    # No phases should be attached as they cannot be calculated.
    phases = []
    for win in windows:
        phases.extend(win.phase_arrivals)

    assert phases == []


def test_event_information_extraction():
    """
    Event information can either be passed or read from sac files.
    """
    config = pyflex.Config(min_period=50.0, max_period=150.0)

    # If not passed, it is read from sac files, if available.
    ws = pyflex.window_selector.WindowSelector(OBS_DATA, SYNTH_DATA, config)
    assert abs(ws.event.latitude - -3.77) <= 1E-5
    assert abs(ws.event.longitude - -77.07) <= 1E-5
    assert abs(ws.event.depth_in_m - 112800.00305) <= 1E-5
    assert ws.event.origin_time == \
        obspy.UTCDateTime(1995, 5, 2, 6, 6, 13, 900000)

    # If it passed, the passed event will be used.
    ev = pyflex.Event(1, 2, 3, obspy.UTCDateTime(2012, 1, 1))
    ws = pyflex.window_selector.WindowSelector(OBS_DATA, SYNTH_DATA, config,
                                               event=ev)
    assert ws.event == ev

    # Alternatively, an ObsPy Catalog or Event object can be passed which
    # opens the gate to more complex workflows.
    cat = obspy.readEvents()
    cat.events = cat.events[:1]
    event = cat[0]

    ev = pyflex.Event(event.origins[0].latitude, event.origins[0].longitude,
                      event.origins[0].depth, event.origins[0].time)

    # Test catalog.
    ws = pyflex.window_selector.WindowSelector(OBS_DATA, SYNTH_DATA, config,
                                               event=cat)
    assert ws.event == ev

    # Test event.
    ws = pyflex.window_selector.WindowSelector(OBS_DATA, SYNTH_DATA, config,
                                               event=cat[0])
    assert ws.event == ev
