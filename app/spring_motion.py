"""Bounded snapshot motion, tuned against Apple's WWDC23 island examples."""
import math

EXPAND_MS = 480
SHRINK_MS = 440
DISMISS_MS = 360


def expand_progress(value):
    t = max(0., min(1., float(value)))
    return 4. * t ** 3 if t < .5 else 1. - (-2. * t + 2.) ** 3 / 2.


def island_response(value):
    """A damped response with zero initial velocity and a small overshoot.

    These are our adaptation parameters, not Apple's unpublished constants.
    Settle before the handoff, avoiding a second one-pixel oscillation.
    """
    t=max(0.,min(1.,float(value)))
    response=1.-math.exp(-8.5*t)*(math.cos(6.5*t)+8.5/6.5*math.sin(6.5*t))
    if t>=.82:return 1.
    settle=stage(t,.58,.82)
    return response+(1.-response)*settle


def stage(value,start,end):
    t=max(0.,min(1.,(float(value)-start)/(end-start)))
    return t*t*(3.-2.*t)


def container_progress(value):
    """Critically damped size changes without a reverse travel at the end.

    A large editor magnifies even a 1.6% spring overshoot into visible motion.
    Inline cards retain their separate, restrained spring response.
    """
    t=max(0.,min(1.,float(value)))
    if t>=.9:return 1.
    response=1.-(1.+9.*t)*math.exp(-9.*t)
    return response+(1.-response)*stage(t,.65,.9)


def dismiss_progress(value):
    """A small initial anticipation, then one uninterrupted disappearance."""
    t = max(0., min(1., float(value)))
    if t<.12:return -.006*stage(t,0.,.12)
    return -.006+1.006*stage(t,.12,1.)
