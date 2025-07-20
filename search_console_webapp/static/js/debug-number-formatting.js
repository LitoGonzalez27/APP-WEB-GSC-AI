/**
 * ✅ ARCHIVO DE DEBUG PARA PROBAR FORMATEO DE NÚMEROS
 * Incluir este script temporalmente para debugging
 */

// Esperar a que el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
  console.log('🧪 INICIANDO TESTS DE FORMATEO DE NÚMEROS');
  
  // Esperar a que number-utils esté disponible
  setTimeout(() => {
    // Importar funciones dinámicamente
    import('./number-utils.js').then(module => {
      const { 
        formatInteger, 
        formatCTR, 
        formatDecimal, 
        formatPosition, 
        formatPercentageChange 
      } = module;
      
      console.log('🧪 Testing formatInteger:');
      console.log('formatInteger(9666):', formatInteger(9666));
      console.log('formatInteger(1234567):', formatInteger(1234567));
      console.log('formatInteger(123):', formatInteger(123));
      
      console.log('🧪 Testing formatCTR:');
      console.log('formatCTR(0.0567):', formatCTR(0.0567));
      console.log('formatCTR(0.1234):', formatCTR(0.1234));
      console.log('formatCTR(0.05):', formatCTR(0.05));
      
      console.log('🧪 Testing formatDecimal:');
      console.log('formatDecimal(5.67, 2):', formatDecimal(5.67, 2));
      console.log('formatDecimal(12.345, 1):', formatDecimal(12.345, 1));
      
      console.log('🧪 Testing formatPosition:');
      console.log('formatPosition(5.2):', formatPosition(5.2));
      console.log('formatPosition(10.75):', formatPosition(10.75));
      
      console.log('🧪 Testing formatPercentageChange:');
      console.log('formatPercentageChange(15.5):', formatPercentageChange(15.5));
      console.log('formatPercentageChange(-8.2):', formatPercentageChange(-8.2));
      
      // Hacer funciones disponibles globalmente para testing manual
      window.debugFormatting = {
        formatInteger,
        formatCTR,
        formatDecimal,
        formatPosition,
        formatPercentageChange
      };
      
      console.log('✅ Funciones de formateo disponibles en window.debugFormatting');
      console.log('🧪 Ejemplo: window.debugFormatting.formatInteger(9666)');
      
    }).catch(error => {
      console.error('❌ Error importando number-utils:', error);
    });
  }, 1000);
}); 