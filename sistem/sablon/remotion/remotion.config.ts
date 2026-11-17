import {Config} from '@remotion/cli/config';

// Fotoğraflar, fontlar proje media/ klasöründe (staticFile('foto/...'), staticFile('fonts/...')).
Config.setPublicDir('../media');
Config.setVideoImageFormat('jpeg');
Config.setJpegQuality(95);
Config.setOverwriteOutput(true);
Config.setCodec('h264');
Config.setCrf(16);
Config.setChromiumOpenGlRenderer('angle'); // @remotion/effects (WebGL2)
