import React from 'react';
import {AbsoluteFill} from 'remotion';
import {C, GoldFrame, Scrim, TitleBlock, useFonts} from '../../../../kit/src';

// Örnek sahne: kit bileşenleriyle format-bilinçli başlık kartı. Bu dosyayı sahneye göre değiştir/sil.
export const Ornek: React.FC = () => {
  useFonts();
  return (
    <AbsoluteFill style={{background: C.ink}}>
      <Scrim />
      <GoldFrame start={2} />
      <TitleBlock title="Proje başlığı" sub="Alt başlık" start={6} anchor="c" />
    </AbsoluteFill>
  );
};
