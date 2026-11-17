import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {TransitionSeries, linearTiming} from '@remotion/transitions';
import {filmBurn} from '@remotion/transitions/film-burn';
import {crossZoom} from '@remotion/transitions/cross-zoom';
import {blurSlide} from '@remotion/transitions/blur-slide';
import {GlowText, GradedPhoto, LightLeakOverlay} from './FxKit';
import {C, sans} from '../theme';
import {useFonts} from '../parts';

const Label: React.FC<{t: string}> = ({t}) => (
  <div style={{position: 'absolute', left: 60, bottom: 50, fontFamily: sans, fontWeight: 600, fontSize: 30, letterSpacing: '0.25em', color: C.goldSoft, textShadow: '0 4px 20px #000'}}>{t}</div>
);

// FxLab: geçiş + efekt kataloğundan örnekler. Kurgu sahnesi değil, skill'in doğrulama/örnek kompozisyonudur.
export const FxLab: React.FC = () => {
  useFonts();
  const f = useCurrentFrame();
  const ca = interpolate(f, [90, 100, 120], [0, 6, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: '#000'}}>
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={90}>
          <GradedPhoto name="salon_sonra" grade="warm" />
          <GlowText text="ÖRNEKOĞLU" />
          <Label t="FILMBURN GECISI" />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={filmBurn()} timing={linearTiming({durationInFrames: 24})} />
        <TransitionSeries.Sequence durationInFrames={90}>
          <GradedPhoto name="cephe_sonra" grade="punchy" ca={ca} />
          <Label t="CHROMATIC ABERRATION + IS GRADING" />
        </TransitionSeries.Sequence>
        <TransitionSeries.Overlay durationInFrames={30}>
          <LightLeakOverlay seed={3} hueShift={20} />
        </TransitionSeries.Overlay>
        <TransitionSeries.Sequence durationInFrames={90}>
          <GradedPhoto name="kut_sonra2" grade="cool" />
          <Label t="LIGHT LEAK BINDIRMESI" />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={crossZoom()} timing={linearTiming({durationInFrames: 24})} />
        <TransitionSeries.Sequence durationInFrames={90}>
          <GradedPhoto name="kut_tavan" grade="neutral" />
          <Label t="CROSSZOOM GECISI" />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={blurSlide()} timing={linearTiming({durationInFrames: 20})} />
        <TransitionSeries.Sequence durationInFrames={60}>
          <GradedPhoto name="salon_sonra" grade="warm" from={{s: 1.0}} to={{s: 1.1}} />
          <Label t="BLURSLIDE GECISI" />
        </TransitionSeries.Sequence>
      </TransitionSeries>
    </AbsoluteFill>
  );
};
