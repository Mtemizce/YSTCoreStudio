import React from 'react';
import {Composition} from 'remotion';
import {Ornek} from './Ornek';

// Kompozisyon kimliği = Kurgu'daki source.unit. Yeni sahne: src/<Ad>.tsx yaz, buraya <Composition> ekle.
// Dikey (9:16) sürümler: width={1080} height={1920}, kit `useFormat()` güvenli alanı kendisi bulur.
export const Root: React.FC = () => (
  <>
    <Composition id="Ornek" component={Ornek} durationInFrames={90} fps={30} width={1920} height={1080} />
  </>
);
