import React from 'react';
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Circle, Rect, Star} from '@remotion/shapes';
import {HtmlInCanvasMotionBlur} from '@remotion/motion-blur';
import {Highlight} from '@remotion/rough-notation';
import {C, serif} from '../theme';
import {useFonts} from '../parts';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

/** Hareket bulanıklığı ile uçan, yay (spring) ile oturan altın şekiller. */
const FlyingShapes: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const sp = (delay: number, damping = 14) => spring({frame: f - delay, fps, config: {damping, stiffness: 120, mass: 0.9}});
  const x1 = interpolate(sp(0), [0, 1], [-300, 520]);
  const x2 = interpolate(sp(8, 18), [0, 1], [2200, 1380]);
  const r = interpolate(f, [0, 90], [0, 220], clamp);
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', left: x1, top: 300, transform: `rotate(${r}deg)`}}>
        <Star points={5} innerRadius={70} outerRadius={150} fill={C.gold} />
      </div>
      <div style={{position: 'absolute', left: x2, top: 560}}>
        <Circle radius={110} fill="none" stroke={C.goldSoft} strokeWidth={10} />
      </div>
      <div style={{position: 'absolute', left: interpolate(sp(16), [0, 1], [-400, 880]), top: 780}}>
        <Rect width={420} height={26} cornerRadius={13} fill={C.paper} />
      </div>
    </AbsoluteFill>
  );
};

export const ObjectsLab: React.FC = () => {
  useFonts();
  const f = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const hl = interpolate(f, [40, 62], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
  return (
    <AbsoluteFill style={{background: C.ink}}>
      <HtmlInCanvasMotionBlur width={width} height={height} samples={10} shutterAngle={240}>
        <FlyingShapes />
      </HtmlInCanvasMotionBlur>
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'flex-start', paddingTop: 110}}>
        <div style={{fontFamily: serif, fontWeight: 700, fontSize: 96, color: C.paper}}>
          Boş bir mekân,{' '}
          <Highlight color="rgba(201,162,77,0.55)" progress={hl}>
            yaşayan bir hikâye
          </Highlight>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
