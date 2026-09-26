import { generateDemo } from '@/lib/demoSignal'

const products = generateDemo()
self.postMessage(products, {
  transfer: [
    products.tile.buffer,
    products.psdDb.buffer,
    products.freqsHz.buffer,
    products.constellation.buffer,
    products.fskInstFreqHz.buffer,
  ],
})
